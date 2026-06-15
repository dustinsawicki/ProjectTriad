"""Seed the v2 Azure SQL datastore for the Claims PoC."""
from __future__ import annotations

import argparse
import json
import os
import random
import struct
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pyodbc
from azure.identity import DefaultAzureCredential
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_DIR = SCRIPT_DIR / ".seed_state"
STATE_DIR.mkdir(exist_ok=True)
MANIFEST_PATH = STATE_DIR / "gen_sql_output.json"
SCHEMA_SQL = (SCRIPT_DIR.parent / "sql" / "schema.sql").read_text(encoding="utf-8")
UUID_NAMESPACE = uuid.UUID("c6e43b1b-f0de-48ce-a6b8-f49beef8d142")
US_STATES = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "MN", "WA", "AZ"]
PDF_DOC_TYPES = {"police_report", "estimate", "medical"}
ADJUSTERS = [
    "alex.morgan@contoso.example",
    "priya.patel@contoso.example",
    "sam.lee@contoso.example",
    "jordan.rivera@contoso.example",
]
DOC_PATTERNS: dict[str, tuple[list[str], list[str]]] = {
    "auto_collision": (["police_report", "estimate", "photo_caption"], ["estimate", "photo_caption"]),
    "auto_comp": (["estimate", "photo_caption", "email"], ["estimate", "photo_caption"]),
    "home_property": (["estimate", "photo_caption", "email"], ["estimate", "email"]),
    "liability": (["police_report", "medical", "email"], ["medical", "email"]),
}
RULES: list[tuple[str, str, str, dict[str, Any], str]] = [
    ("FAIR-001", "fair_claims", "Acknowledge FNOL within 15 calendar days.", {"max_ack_days": 15}, "1.0"),
    ("FAIR-002", "fair_claims", "Communicate coverage decision within 40 days of completed proof of loss.", {"max_decision_days": 40}, "1.0"),
    ("FAIR-003", "fair_claims", "Provide written denial with statutory citation.", {"requires": ["citation", "appeal_rights"]}, "1.0"),
    ("LIMIT-001", "coverage_limit", "Settlement shall not exceed policy property damage limit.", {"check": "settlement <= coverage.property_damage"}, "1.0"),
    ("LIMIT-002", "coverage_limit", "Settlement shall not exceed bodily injury per-person limit.", {"check": "settlement <= coverage.bodily_injury_per_person"}, "1.0"),
    ("LIMIT-003", "coverage_limit", "Auto comprehensive subject to deductible.", {"apply": "deductible.comprehensive"}, "1.0"),
    ("ANTI-001", "anti_discrim", "Decision rationale must not reference protected class attributes.", {"forbid_terms": ["age", "race", "national origin", "religion", "gender", "zip code"]}, "1.0"),
    ("ANTI-002", "anti_discrim", "Decision must not denominate party by surname alone.", {"forbid_pattern": "surname_only"}, "1.0"),
    ("STATE-TX-001", "state_reg", "TX prompt-pay: settle within 60 days of acceptance.", {"state": "TX", "max_settle_days": 60}, "1.0"),
    ("STATE-CA-001", "state_reg", "CA: written acknowledgement within 15 days.", {"state": "CA", "max_ack_days": 15}, "1.0"),
    ("STATE-FL-001", "state_reg", "FL: pay or deny within 90 days after notice of loss.", {"state": "FL", "max_decision_days": 90}, "1.0"),
    ("SIU-001", "fair_claims", "Refer to SIU when fraud score >= 0.70.", {"siu_threshold": 0.70}, "1.0"),
    ("DOC-001", "fair_claims", "Require police report for auto collisions with damage > $5,000.", {"trigger": {"loss_type": "auto_collision", "damage_gt": 5000}, "require": "police_report"}, "1.0"),
    ("DOC-002", "fair_claims", "Require itemized estimate for any property damage claim.", {"require": "estimate"}, "1.0"),
    ("RES-001", "coverage_limit", "Reserve must be set within 5 business days of triage.", {"max_reserve_days": 5}, "1.0"),
    ("SUB-001", "fair_claims", "Pursue subrogation when third-party fault probability > 0.6.", {"sub_threshold": 0.6}, "1.0"),
    ("AI-001", "fair_claims", "All AI decisions require human approval before payment.", {"requires_human": True, "before": "payment"}, "1.0"),
    ("AI-002", "fair_claims", "Every AI decision must record model name, version, and rationale.", {"requires": ["model", "version", "rationale"]}, "1.0"),
    ("AI-003", "fair_claims", "Settlement recommendations must cite supporting documents by id.", {"requires": "document_citations"}, "1.0"),
    ("DENY-001", "fair_claims", "Denials must enumerate every coverage clause considered.", {"requires": "clauses_considered"}, "1.0"),
    ("FRAUD-001", "fair_claims", "Shared identifiers across >2 unrelated claims warrants link review.", {"shared_id_threshold": 2}, "1.0"),
    ("FRAUD-002", "fair_claims", "Late-night loss within 7 days of policy bind raises severity.", {"window_days": 7, "night_hours": [22, 23, 0, 1, 2, 3, 4]}, "1.0"),
    ("EST-001", "coverage_limit", "Estimate variance > 35% vs. comparable repairs requires SIU review.", {"variance_threshold": 0.35}, "1.0"),
    ("MED-001", "coverage_limit", "Medical bill review required for charges > $2,500.", {"med_review_threshold": 2500}, "1.0"),
    ("AUDIT-001", "fair_claims", "Audit events are append-only; no modification permitted.", {"append_only": True}, "1.0"),
]
DEMO_CLAIMS: list[dict[str, Any]] = [
    {"claim_number": "CLM-200001", "loss_type": "auto_collision", "photos": 2, "doc_types": ["police_report", "estimate", "photo_caption", "photo_caption"], "api_flags": ["weather", "avm", "payment"], "telematics_hints": {"hard_brake": -4}, "demo_intent": "Happy path"},
    {"claim_number": "CLM-200002", "loss_type": "home_property", "photos": 3, "doc_types": ["estimate", "photo_caption", "photo_caption", "photo_caption"], "api_flags": ["weather", "avm", "payment"], "telematics_hints": {}, "demo_intent": "Citations"},
    {"claim_number": "CLM-200003", "loss_type": "auto_collision", "photos": 3, "doc_types": ["police_report", "estimate", "photo_caption", "photo_caption", "photo_caption"], "api_flags": ["weather", "avm", "iso", "payment"], "telematics_hints": {"crash_g": 0, "hard_brake": -3}, "demo_intent": "Telematics evidence"},
    {"claim_number": "CLM-200004", "loss_type": "auto_collision", "photos": 2, "doc_types": ["estimate", "photo_caption", "photo_caption"], "api_flags": ["avm", "medbill"], "telematics_hints": {"normal": True}, "demo_intent": "Guardrail block"},
    {"claim_number": "CLM-200005", "loss_type": "auto_collision", "photos": 2, "doc_types": ["police_report", "estimate", "photo_caption", "photo_caption"], "api_flags": ["weather", "police", "avm"], "telematics_hints": {"normal": True}, "demo_intent": "Subrogation"},
    {"claim_number": "CLM-200006", "loss_type": "liability", "photos": 1, "doc_types": ["medical", "medical", "medical", "estimate", "photo_caption"], "api_flags": ["medbill"], "telematics_hints": {}, "demo_intent": "Medical bill review"},
    {"claim_number": "CLM-200007", "loss_type": "liability", "photos": 0, "doc_types": ["police_report", "medical"], "api_flags": ["iso", "medbill"], "telematics_hints": {}, "demo_intent": "Liability"},
    {"claim_number": "CLM-200008", "loss_type": "auto_collision", "photos": 2, "doc_types": ["estimate", "photo_caption", "photo_caption"], "api_flags": ["iso", "link-graph"], "telematics_hints": {"hard_brake": -1, "impact": False}, "demo_intent": "Fraud ring"},
    {"claim_number": "CLM-200009", "loss_type": "auto_collision", "photos": 1, "doc_types": ["estimate", "photo_caption"], "api_flags": ["iso", "link-graph"], "telematics_hints": {}, "demo_intent": "Same ring"},
    {"claim_number": "CLM-200010", "loss_type": "auto_collision", "photos": 1, "doc_types": ["estimate", "photo_caption"], "api_flags": ["iso", "link-graph"], "telematics_hints": {}, "demo_intent": "Full 3-node graph"},
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server-fqdn", default=os.getenv("SQL_SERVER_FQDN"))
    parser.add_argument("--database-name", default=os.getenv("SQL_DATABASE_NAME"))
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    if not args.server_fqdn or not args.database_name:
        parser.error("SQL_SERVER_FQDN and SQL_DATABASE_NAME are required via args or env vars.")
    return args


def stable_uuid(*parts: object) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, "::".join(str(part) for part in parts)))


def blob_url(container: str, path: str) -> str:
    account_name = os.getenv("BLOB_ACCOUNT_NAME", "placeholderclaimsblob")
    return f"https://{account_name}.blob.core.windows.net/{container}/{path}"


def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(exclude_interactive_browser_credential=False)


def _access_token_struct() -> dict[int, bytes]:
    token = _credential().get_token("https://database.windows.net/.default").token
    encoded = b"".join(bytes([byte]) + b"\0" for byte in token.encode("utf-8"))
    return {1256: struct.pack("=i", len(encoded)) + encoded}


def connect(server_fqdn: str, database_name: str) -> pyodbc.Connection:
    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={server_fqdn},1433;"
        f"DATABASE={database_name};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )
    print("[gen_sql] Connecting to Azure SQL ...")
    return pyodbc.connect(connection_string, attrs_before=_access_token_struct())


def apply_schema(conn: pyodbc.Connection) -> None:
    print("[gen_sql] Applying schema ...")
    cursor = conn.cursor()
    for batch in SCHEMA_SQL.split("\nGO\n"):
        if batch.strip():
            cursor.execute(batch)
    cursor.execute(
        """
        IF COL_LENGTH('dbo.Document', 'BlobUrl') IS NULL
            ALTER TABLE dbo.Document ADD BlobUrl NVARCHAR(400) NULL;
        """
    )
    conn.commit()


def build_policies() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    for index in range(5000):
        policy_number = f"POL-{200001 + index}"
        if index < 800:
            product_line = "auto"
            status = "active"
        else:
            product_line = random.choices(["auto", "home", "umbrella"], weights=[0.62, 0.33, 0.05], k=1)[0]
            status = random.choices(["active", "lapsed", "cancelled"], weights=[0.90, 0.07, 0.03], k=1)[0]
        effective = fake.date_between(start_date="-3y", end_date="-30d")
        expiration = effective + timedelta(days=365)
        state = US_STATES[index % len(US_STATES)]
        coverage: dict[str, Any] = {
            "state": state,
            "bodily_injury_per_person": int(random.choice([25000, 50000, 100000, 250000])),
            "bodily_injury_per_accident": int(random.choice([50000, 100000, 300000, 500000])),
            "property_damage": int(random.choice([25000, 50000, 100000])),
        }
        if product_line == "auto":
            coverage.update(
                {
                    "collision_deductible": int(random.choice([250, 500, 1000])),
                    "comprehensive_deductible": int(random.choice([250, 500, 1000])),
                    "vehicle_count": int(random.choice([1, 1, 2, 2, 3])),
                }
            )
        elif product_line == "home":
            coverage.update(
                {
                    "dwelling_limit": int(random.choice([250000, 350000, 500000, 750000])),
                    "water_backup_limit": int(random.choice([10000, 25000, 50000])),
                }
            )
        else:
            coverage["umbrella_limit"] = int(random.choice([1000000, 2000000, 5000000]))
        policies.append(
            {
                "PolicyId": stable_uuid("policy", policy_number),
                "PolicyNumber": policy_number,
                "ProductLine": product_line,
                "EffectiveDate": effective,
                "ExpirationDate": expiration,
                "PremiumAnnual": round(random.uniform(425, 4850), 2),
                "CoverageJson": json.dumps(coverage),
                "Status": status,
                "State": state,
            }
        )
    return policies


def build_rings() -> list[dict[str, Any]]:
    rings: list[dict[str, Any]] = []
    for index in range(30):
        state = US_STATES[index % len(US_STATES)]
        rings.append(
            {
                "ring_id": f"RING-{index + 1:03d}",
                "shared_phone": f"555-77{index // 10}{index % 10}-{1000 + index:04d}",
                "shared_address": {
                    "street": f"{500 + index} Shadow Creek Ln",
                    "city": fake.city(),
                    "state": state,
                    "zip": f"{75000 + index}",
                },
                "shared_vin_prefix": f"1HGBH41JX{index:02d}",
                "members": [],
            }
        )
    return rings


def build_parties(rings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    for index in range(8000):
        role = random.choices(["insured", "claimant", "witness", "provider"], weights=[0.56, 0.26, 0.10, 0.08], k=1)[0]
        state = US_STATES[index % len(US_STATES)]
        address = {"street": fake.street_address(), "city": fake.city(), "state": state, "zip": fake.postcode()}
        phone = fake.numerify("###-###-####")
        ring_id: str | None = None
        if index < 120:
            ring = rings[index // 4]
            ring_id = ring["ring_id"]
            address = dict(ring["shared_address"])
            phone = ring["shared_phone"]
        party_id = stable_uuid("party", index + 1)
        party = {
            "PartyId": party_id,
            "Role": role,
            "FullName": fake.name(),
            "Email": fake.email(),
            "Phone": phone,
            "AddressJson": json.dumps(address),
            "DOB": fake.date_of_birth(minimum_age=21, maximum_age=84),
            "RingId": ring_id,
            "State": address["state"],
        }
        parties.append(party)
        if ring_id:
            rings[index // 4]["members"].append({"party_id": party_id, "name": party["FullName"]})
    return parties


def _auto_policy(policies: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    auto_policies = [policy for policy in policies if policy["ProductLine"] == "auto" and policy["Status"] == "active"]
    return auto_policies[offset]


def _home_policy(policies: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    home_policies = [policy for policy in policies if policy["ProductLine"] == "home" and policy["Status"] == "active"]
    return home_policies[offset]


def _liability_policy(policies: list[dict[str, Any]], offset: int) -> dict[str, Any]:
    liability_policies = [policy for policy in policies if policy["ProductLine"] in {"auto", "home", "umbrella"} and policy["Status"] == "active"]
    return liability_policies[offset]


def build_demo_claims(policies: list[dict[str, Any]], parties: list[dict[str, Any]], rings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    demo_claims: list[dict[str, Any]] = []
    ring_map = {
        "CLM-200008": (rings[0], 0),
        "CLM-200009": (rings[0], 1),
        "CLM-200010": (rings[0], 2),
    }
    for index, config in enumerate(DEMO_CLAIMS, start=1):
        if config["loss_type"] == "home_property":
            policy = _home_policy(policies, index * 3)
        elif config["loss_type"] == "liability":
            policy = _liability_policy(policies, 100 + index)
        else:
            policy = _auto_policy(policies, 10 + index)
        state = json.loads(policy["CoverageJson"])["state"]
        zip_code = f"{73300 + index}"
        address = {"street": fake.street_address(), "city": fake.city(), "state": state, "zip": zip_code}
        phone = fake.numerify("###-###-####")
        vin = f"1FTFW1E5X{index:08d}"[:17]
        party_ids = [parties[200 + index]["PartyId"], parties[400 + index]["PartyId"]]
        ring_id: str | None = None
        if config["claim_number"] in ring_map:
            ring, member_index = ring_map[config["claim_number"]]
            ring_id = ring["ring_id"]
            address = dict(ring["shared_address"])
            phone = ring["shared_phone"]
            vin = f"{ring['shared_vin_prefix']}{member_index + 1:05d}"[:17]
            party_ids = [member["party_id"] for member in ring["members"]]
        loss_dt = datetime.now(UTC) - timedelta(days=10 + index, hours=index)
        reported_amount = 18850.0 if config["claim_number"] == "CLM-200004" else round(random.uniform(2200, 14500), 2)
        reserve_amount = 10450.0 if config["claim_number"] == "CLM-200006" else round(reported_amount * random.uniform(0.92, 1.18), 2)
        settled_amount = round(reserve_amount * random.uniform(0.75, 0.96), 2) if index <= 3 else None
        demo_claims.append(
            {
                "ClaimId": stable_uuid("claim", config["claim_number"]),
                "PolicyId": policy["PolicyId"],
                "PolicyNumber": policy["PolicyNumber"],
                "ClaimNumber": config["claim_number"],
                "LossDateTime": loss_dt.replace(tzinfo=None),
                "LossType": config["loss_type"],
                "Status": "settled" if settled_amount else "assessed",
                "ReportedAmount": reported_amount,
                "ReserveAmount": reserve_amount,
                "SettledAmount": settled_amount,
                "TriageDecisionJson": json.dumps({"route": "desk", "reason": config["demo_intent"], "seed": SEED}),
                "AssignedAdjuster": ADJUSTERS[index % len(ADJUSTERS)],
                "State": state,
                "ZipCode": zip_code,
                "Address": address,
                "Phone": phone,
                "Vin": vin,
                "PartyIds": party_ids,
                "RingId": ring_id,
                "PhotoCount": config["photos"],
                "DocTypes": list(config["doc_types"]),
                "ApiFlags": list(config["api_flags"]),
                "TelematicsHints": dict(config["telematics_hints"]),
                "DemoIntent": config["demo_intent"],
            }
        )
    return demo_claims


def build_regular_claims(policies: list[dict[str, Any]], parties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_policies = [policy for policy in policies if policy["Status"] == "active"]
    claims: list[dict[str, Any]] = []
    for offset in range(1990):
        claim_number = f"CLM-{200011 + offset}"
        policy = active_policies[(offset * 13) % len(active_policies)]
        product = policy["ProductLine"]
        loss_type = random.choices(
            ["auto_collision", "auto_comp", "liability"] if product == "auto" else ["home_property", "liability"] if product == "home" else ["liability"],
            weights=[0.70, 0.15, 0.15] if product == "auto" else [0.88, 0.12] if product == "home" else [1.0],
            k=1,
        )[0]
        loss_dt = datetime.now(UTC) - timedelta(days=int(RNG.integers(15, 720)), hours=int(RNG.integers(0, 23)), minutes=int(RNG.integers(0, 59)))
        reported_amount = max(round(float(RNG.normal(6200, 2400)), 2), 650.0)
        status = random.choices(["open", "triaged", "assessed", "settled", "denied"], weights=[0.10, 0.18, 0.26, 0.40, 0.06], k=1)[0]
        reserve_amount = round(reported_amount * random.uniform(0.90, 1.20), 2) if status != "open" else None
        settled_amount = round(reserve_amount * random.uniform(0.72, 0.98), 2) if status == "settled" and reserve_amount else None
        state = json.loads(policy["CoverageJson"])["state"]
        zip_code = f"{70000 + (offset % 900):05d}"
        claims.append(
            {
                "ClaimId": stable_uuid("claim", claim_number),
                "PolicyId": policy["PolicyId"],
                "PolicyNumber": policy["PolicyNumber"],
                "ClaimNumber": claim_number,
                "LossDateTime": loss_dt.replace(tzinfo=None),
                "LossType": loss_type,
                "Status": status,
                "ReportedAmount": reported_amount,
                "ReserveAmount": reserve_amount,
                "SettledAmount": settled_amount,
                "TriageDecisionJson": None,
                "AssignedAdjuster": ADJUSTERS[offset % len(ADJUSTERS)],
                "State": state,
                "ZipCode": zip_code,
                "Address": {"street": fake.street_address(), "city": fake.city(), "state": state, "zip": zip_code},
                "Phone": parties[(offset * 3) % len(parties)]["Phone"],
                "Vin": f"2C3KA43R7{offset:08d}"[:17] if product == "auto" else None,
                "PartyIds": [parties[(offset * 2) % len(parties)]["PartyId"], parties[(offset * 2 + 1) % len(parties)]["PartyId"]],
                "RingId": None,
                "PhotoCount": 3 if offset < 190 else random.choice([0, 1, 2]),
                "DocTypes": [],
                "ApiFlags": [],
                "TelematicsHints": {},
                "DemoIntent": None,
            }
        )
    return claims


def _document_slug(doc_type: str, ordinal: int) -> str:
    return doc_type if ordinal == 1 else f"{doc_type}-{ordinal}"


def _render_document_text(doc_type: str, claim: dict[str, Any], ordinal: int) -> str:
    when = claim["LossDateTime"]
    if doc_type == "police_report":
        return "\n".join(
            [
                "Police Incident Report",
                f"Claim: {claim['ClaimNumber']}",
                f"Loss Type: {claim['LossType']}",
                f"Date/Time: {when:%Y-%m-%d %H:%M}",
                f"Officer: {fake.name()}",
                f"Location: {claim['Address']['street']}, {claim['Address']['city']}, {claim['Address']['state']} {claim['Address']['zip']}",
                f"Narrative: Responded to a reported {claim['LossType'].replace('_', ' ')} involving VIN {claim['Vin'] or 'N/A'}.",
            ]
        )
    if doc_type == "estimate":
        subtotal = round(claim["ReportedAmount"] * 0.88 + ordinal * 173.0, 2)
        tax = round(subtotal * 0.0825, 2)
        return "\n".join(
            [
                "Repair Estimate",
                f"Claim: {claim['ClaimNumber']}",
                f"Shop: {fake.company()} Collision Center",
                f"Labor: ${round(subtotal * 0.42, 2):,.2f}",
                f"Parts: ${round(subtotal * 0.38, 2):,.2f}",
                f"Paint: ${round(subtotal * 0.20, 2):,.2f}",
                f"Tax: ${tax:,.2f}",
                f"Total: ${round(subtotal + tax, 2):,.2f}",
            ]
        )
    if doc_type == "medical":
        charge = round(325 + ordinal * 880 + random.uniform(0, 450), 2)
        return "\n".join(
            [
                "Medical Bill",
                f"Claim: {claim['ClaimNumber']}",
                f"Patient: {fake.name()}",
                f"Provider: {fake.company()} Orthopedics",
                f"CPT: {random.choice(['99213', '97110', '72141', '97014'])}",
                f"Charge: ${charge:,.2f}",
            ]
        )
    if doc_type == "photo_caption":
        return "\n".join(
            [
                "Damage Photo Caption",
                f"Claim: {claim['ClaimNumber']}",
                f"Photo {ordinal} shows {random.choice(['driver-side dent', 'rear bumper scrape', 'ceiling water stain', 'broken glass'])}.",
                f"Captured near {when:%Y-%m-%d %H:%M}.",
            ]
        )
    return "\n".join(
        [
            "Claim Correspondence",
            f"Claim: {claim['ClaimNumber']}",
            f"Loss Type: {claim['LossType']}",
            "Insured requested a status update and provided additional narrative context.",
        ]
    )


def build_documents(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    three_doc_claims = {claim["ClaimNumber"] for claim in claims[10 : 10 + 1295]}
    pdf_blob_budget = 800
    for claim in claims:
        if not claim["DocTypes"]:
            claim["DocTypes"] = list(DOC_PATTERNS[claim["LossType"]][0 if claim["ClaimNumber"] in three_doc_claims else 1])
        counters: Counter[str] = Counter()
        for doc_type in claim["DocTypes"]:
            counters[doc_type] += 1
            ordinal = counters[doc_type]
            blob = None
            if doc_type == "photo_caption" and claim["PhotoCount"] >= ordinal:
                blob = blob_url("photos", f"{claim['ClaimNumber']}/photo-{ordinal}.jpg")
            elif doc_type in PDF_DOC_TYPES and pdf_blob_budget > 0:
                blob = blob_url("documents", f"{claim['ClaimNumber']}/{_document_slug(doc_type, ordinal)}.pdf")
                pdf_blob_budget -= 1
            documents.append(
                {
                    "DocumentId": stable_uuid("document", claim["ClaimNumber"], doc_type, ordinal),
                    "ClaimId": claim["ClaimId"],
                    "ClaimNumber": claim["ClaimNumber"],
                    "DocType": doc_type,
                    "Title": _document_slug(doc_type, ordinal).replace("_", " ").title(),
                    "RawText": _render_document_text(doc_type, claim, ordinal),
                    "ExtractedJson": json.dumps({"source": "seed_v2", "ordinal": ordinal}),
                    "BlobUrl": blob,
                }
            )
    assert len(documents) == 5309, f"Expected 5309 docs, got {len(documents)}"
    return documents


def build_fraud_signals(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    positive_claims = claims[7:10] + random.sample(claims[10:], 147)
    double_signal_claims = {claim["ClaimNumber"] for claim in positive_claims[:77]}
    signals: list[dict[str, Any]] = []
    for claim in positive_claims:
        patterns = [
            ("link_analysis", round(random.uniform(0.74, 0.97), 4), {"reason": "Shared phone/address/VIN pattern", "rule": "FRAUD-001", "ring_id": claim.get("RingId")}),
            ("rule", round(random.uniform(0.68, 0.91), 4), {"reason": "Late-night or early-bind anomaly", "rule": "FRAUD-002"}),
        ]
        chosen = patterns if claim["ClaimNumber"] in double_signal_claims else patterns[:1]
        for index, (signal_type, score, rationale) in enumerate(chosen, start=1):
            signals.append(
                {
                    "SignalId": stable_uuid("fraud_signal", claim["ClaimNumber"], index),
                    "ClaimId": claim["ClaimId"],
                    "SignalType": signal_type,
                    "Score": score,
                    "RationaleJson": json.dumps(rationale),
                }
            )
    for claim in random.sample([claim for claim in claims if claim not in positive_claims], 700):
        signals.append(
            {
                "SignalId": stable_uuid("fraud_signal_low", claim["ClaimNumber"]),
                "ClaimId": claim["ClaimId"],
                "SignalType": "rule",
                "Score": round(random.uniform(0.05, 0.33), 4),
                "RationaleJson": json.dumps({"reason": "Baseline rules checked; no anomaly.", "rule": "FRAUD-001"}),
            }
        )
    assert len(signals) == 927, f"Expected 927 fraud signals, got {len(signals)}"
    return signals


def build_decisions(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for claim in claims[:10]:
        blocked = claim["ClaimNumber"] in {"CLM-200004", "CLM-200008"}
        decisions.append(
            {
                "DecisionId": stable_uuid("decision", claim["ClaimNumber"], "triage"),
                "ClaimId": claim["ClaimId"],
                "AgentName": "TriageCoverageAgent",
                "DecisionType": "coverage",
                "PayloadJson": json.dumps({"route": "desk", "reason": claim["DemoIntent"], "model": "gpt-4o", "version": "2024-08-06"}),
                "Status": "blocked" if blocked else "approved",
            }
        )
        decisions.append(
            {
                "DecisionId": stable_uuid("decision", claim["ClaimNumber"], "assessment"),
                "ClaimId": claim["ClaimId"],
                "AgentName": "AssessmentSettlementAgent",
                "DecisionType": "settlement",
                "PayloadJson": json.dumps({"settlement_amount": claim["ReserveAmount"] or claim["ReportedAmount"], "citations": claim["DocTypes"][:2], "model": "gpt-4o", "version": "2024-08-06"}),
                "Status": "proposed" if blocked else "approved",
            }
        )
    return decisions


def build_audit_events(claims: list[dict[str, Any]], decisions: list[dict[str, Any]], rule_id_map: dict[str, str]) -> list[dict[str, Any]]:
    audit_events: list[dict[str, Any]] = []
    decisions_by_claim: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        decisions_by_claim[decision["ClaimId"]].append(decision)
    event_index = 0
    for claim in claims[:10]:
        for decision in decisions_by_claim[claim["ClaimId"]]:
            rule_code = "LIMIT-001" if decision["DecisionType"] == "settlement" else "AI-002"
            audit_events.append(
                {
                    "EventId": stable_uuid("audit-demo", claim["ClaimNumber"], decision["DecisionType"]),
                    "ClaimId": claim["ClaimId"],
                    "DecisionId": decision["DecisionId"],
                    "RuleId": rule_id_map[rule_code],
                    "Actor": "agent",
                    "ActorName": decision["AgentName"],
                    "Action": f"{decision['DecisionType']}.evaluate",
                    "Outcome": "block" if decision["Status"] in {"blocked", "proposed"} else "pass",
                    "RationaleJson": json.dumps({"rule": rule_code, "claim": claim["ClaimNumber"], "seed": SEED}),
                    "CorrelationId": f"corr-{claim['ClaimNumber']}",
                }
            )
            event_index += 1
    while len(audit_events) < 4006:
        claim = claims[event_index % len(claims)]
        actor = "human" if event_index % 3 == 0 else "agent"
        rule_code = ["FAIR-001", "FAIR-002", "AI-002", "AUDIT-001"][event_index % 4]
        audit_events.append(
            {
                "EventId": stable_uuid("audit", event_index, claim["ClaimNumber"]),
                "ClaimId": claim["ClaimId"],
                "DecisionId": None,
                "RuleId": rule_id_map[rule_code],
                "Actor": actor,
                "ActorName": claim["AssignedAdjuster"] if actor == "human" else random.choice(["FnolDocumentAgent", "TriageCoverageAgent", "GuardrailsAgent"]),
                "Action": ["fnol.acknowledge", "triage.review", "assessment.review", "guardrail.check"][event_index % 4],
                "Outcome": random.choice(["pass", "approve", "edit"]),
                "RationaleJson": json.dumps({"rule": rule_code, "ordinal": event_index, "version": "1.0"}),
                "CorrelationId": f"corr-{claim['ClaimNumber']}-{event_index:04d}",
            }
        )
        event_index += 1
    return audit_events


def persist_manifest(path: Path, *, policies: list[dict[str, Any]], parties: list[dict[str, Any]], claims: list[dict[str, Any]], documents: list[dict[str, Any]], fraud_signals: list[dict[str, Any]], rings: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "seed": SEED,
        "generated_utc": datetime.now(UTC).isoformat(),
        "counts": {
            "policies": len(policies),
            "parties": len(parties),
            "claims": len(claims),
            "documents": len(documents),
            "fraud_signals": len(fraud_signals),
            "fraud_rings": len(rings),
        },
        "policies": [{"policy_id": policy["PolicyId"], "policy_number": policy["PolicyNumber"], "product_line": policy["ProductLine"], "state": policy["State"], "status": policy["Status"]} for policy in policies],
        "ring_parties": [{"party_id": party["PartyId"], "phone": party["Phone"], "state": party["State"], "ring_id": party["RingId"]} for party in parties if party["RingId"]],
        "claims": [
            {
                "claim_id": claim["ClaimId"],
                "claim_number": claim["ClaimNumber"],
                "policy_id": claim["PolicyId"],
                "policy_number": claim["PolicyNumber"],
                "loss_datetime": claim["LossDateTime"].isoformat(),
                "loss_type": claim["LossType"],
                "state": claim["State"],
                "zip_code": claim["ZipCode"],
                "address": claim["Address"],
                "phone": claim["Phone"],
                "vin": claim["Vin"],
                "party_ids": claim["PartyIds"],
                "ring_id": claim["RingId"],
                "photo_count": claim["PhotoCount"],
                "doc_types": claim["DocTypes"],
                "api_flags": claim["ApiFlags"],
                "demo_intent": claim["DemoIntent"],
                "telematics_hints": claim["TelematicsHints"],
            }
            for claim in claims
        ],
        "documents": [{"document_id": document["DocumentId"], "claim_number": document["ClaimNumber"], "doc_type": document["DocType"], "blob_url": document["BlobUrl"]} for document in documents],
        "fraud_rings": rings,
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def insert_many(cursor: pyodbc.Cursor, sql: str, rows: Iterable[tuple[Any, ...]]) -> None:
    items = list(rows)
    cursor.fast_executemany = True
    cursor.executemany(sql, items)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_sql] Deterministic seed={SEED}")
    policies = build_policies()
    rings = build_rings()
    parties = build_parties(rings)
    claims = build_demo_claims(policies, parties, rings) + build_regular_claims(policies, parties)
    documents = build_documents(claims)
    fraud_signals = build_fraud_signals(claims)
    decisions = build_decisions(claims)
    rule_id_map = {code: stable_uuid("rule", code) for code, *_ in RULES}
    audit_events = build_audit_events(claims, decisions, rule_id_map)
    assert len({signal["ClaimId"] for signal in fraud_signals if signal["Score"] >= 0.68}) == 150

    conn = connect(args.server_fqdn, args.database_name)
    try:
        apply_schema(conn)
        cursor = conn.cursor()
        print("[gen_sql] Inserting policy rules ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.PolicyRule (RuleId, RuleCode, Category, Description, PredicateJson, Version, IsActive) VALUES (?,?,?,?,?,?,1)",
            ((rule_id_map[code], code, category, description, json.dumps(predicate), version) for code, category, description, predicate, version in RULES),
        )
        print("[gen_sql] Inserting policies ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.Policy (PolicyId, PolicyNumber, ProductLine, EffectiveDate, ExpirationDate, PremiumAnnual, CoverageJson, Status) VALUES (?,?,?,?,?,?,?,?)",
            ((policy["PolicyId"], policy["PolicyNumber"], policy["ProductLine"], policy["EffectiveDate"], policy["ExpirationDate"], policy["PremiumAnnual"], policy["CoverageJson"], policy["Status"]) for policy in policies),
        )
        print("[gen_sql] Inserting parties ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.Party (PartyId, Role, FullName, Email, Phone, AddressJson, DOB) VALUES (?,?,?,?,?,?,?)",
            ((party["PartyId"], party["Role"], party["FullName"], party["Email"], party["Phone"], party["AddressJson"], party["DOB"]) for party in parties),
        )
        print("[gen_sql] Inserting claims ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.Claim (ClaimId, PolicyId, ClaimNumber, LossDateTime, LossType, Status, ReportedAmount, ReserveAmount, SettledAmount, TriageDecisionJson, AssignedAdjuster) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ((claim["ClaimId"], claim["PolicyId"], claim["ClaimNumber"], claim["LossDateTime"], claim["LossType"], claim["Status"], claim["ReportedAmount"], claim["ReserveAmount"], claim["SettledAmount"], claim["TriageDecisionJson"], claim["AssignedAdjuster"]) for claim in claims),
        )
        print("[gen_sql] Inserting documents ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.Document (DocumentId, ClaimId, DocType, Title, RawText, ExtractedJson, BlobUrl) VALUES (?,?,?,?,?,?,?)",
            ((document["DocumentId"], document["ClaimId"], document["DocType"], document["Title"], document["RawText"], document["ExtractedJson"], document["BlobUrl"]) for document in documents),
        )
        print("[gen_sql] Inserting fraud signals ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.FraudSignal (SignalId, ClaimId, SignalType, Score, RationaleJson) VALUES (?,?,?,?,?)",
            ((signal["SignalId"], signal["ClaimId"], signal["SignalType"], signal["Score"], signal["RationaleJson"]) for signal in fraud_signals),
        )
        print("[gen_sql] Inserting agent decisions ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.AgentDecision (DecisionId, ClaimId, AgentName, DecisionType, PayloadJson, Status) VALUES (?,?,?,?,?,?)",
            ((decision["DecisionId"], decision["ClaimId"], decision["AgentName"], decision["DecisionType"], decision["PayloadJson"], decision["Status"]) for decision in decisions),
        )
        print("[gen_sql] Inserting audit events ...")
        insert_many(
            cursor,
            "INSERT INTO dbo.AuditEvent (EventId, ClaimId, DecisionId, RuleId, Actor, ActorName, Action, Outcome, RationaleJson, CorrelationId) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ((event["EventId"], event["ClaimId"], event["DecisionId"], event["RuleId"], event["Actor"], event["ActorName"], event["Action"], event["Outcome"], event["RationaleJson"], event["CorrelationId"]) for event in audit_events),
        )
        conn.commit()
    finally:
        conn.close()

    persist_manifest(args.manifest_path, policies=policies, parties=parties, claims=claims, documents=documents, fraud_signals=fraud_signals, rings=rings)
    print(f"[gen_sql] Wrote manifest to {args.manifest_path}")
    summary = {
        "generator": "gen_sql",
        "policies": len(policies),
        "parties": len(parties),
        "claims": len(claims),
        "documents": len(documents),
        "fraud_signals": len(fraud_signals),
        "audit_events": len(audit_events),
        "policy_rules": len(RULES),
        "demo_claims": 10,
    }
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
