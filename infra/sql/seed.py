"""
Synthetic dataset seeder for the Agentic Claims Processing PoC.

Generates a realistic-but-fake P&C book:
- 5,000 policies (auto/home/umbrella)
- ~8,000 parties (insureds + claimants + providers + witnesses)
- 2,000 claims across the funnel
- ~6,000 documents (2-4 per claim) with templated narrative text
- 25 policy rules (fair-claims, state-reg, coverage-limit, anti-discrim)
- 150-claim "fraud-positive" subset with shared identifiers (rings)
- ~10,000 backfilled audit events

Deterministic via random.seed(42) / Faker.seed(42).

Run via run-seed.ps1 / run-seed.sh (which inject env vars and call this).
"""
from __future__ import annotations

import json
import os
import random
import struct
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pyodbc
from azure.identity import DefaultAzureCredential
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")

SQL_SERVER   = os.environ["SQL_SERVER_FQDN"]
SQL_DATABASE = os.environ["SQL_DATABASE_NAME"]
RESEED       = os.environ.get("RESEED", "0") == "1"

SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_SQL = (SCRIPT_DIR / "schema.sql").read_text(encoding="utf-8")

# ---- Connection ----------------------------------------------------------

def _connect() -> pyodbc.Connection:
    """Connect to Azure SQL using DefaultAzureCredential (Entra)."""
    cred = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    token = cred.get_token("https://database.windows.net/.default").token
    # Encode for SQL_COPT_SS_ACCESS_TOKEN
    exptoken = b""
    for i in bytes(token, "utf-8"):
        exptoken += bytes([i]) + b"\0"
    token_struct = struct.pack("=i", len(exptoken)) + exptoken
    SQL_COPT_SS_ACCESS_TOKEN = 1256

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SQL_SERVER},1433;"
        f"DATABASE={SQL_DATABASE};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
    )
    return pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

# ---- Schema + truncate ---------------------------------------------------

def apply_schema(conn: pyodbc.Connection) -> None:
    print("[seed] Applying schema.sql ...")
    cur = conn.cursor()
    for batch in SCHEMA_SQL.split("\nGO\n"):
        if batch.strip():
            cur.execute(batch)
    conn.commit()

def truncate_all(conn: pyodbc.Connection) -> None:
    print("[seed] Truncating existing data ...")
    cur = conn.cursor()
    cur.execute("EXEC dbo.usp_TruncateAll")
    conn.commit()

# ---- Generators ----------------------------------------------------------

US_STATES = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "MN", "WA", "AZ"]
PRODUCT_LINES = ["auto"] * 70 + ["home"] * 25 + ["umbrella"] * 5
LOSS_TYPES_BY_PRODUCT = {
    "auto":     ["auto_collision"] * 6 + ["auto_comp"] * 2 + ["liability"] * 2,
    "home":     ["home_property"] * 9 + ["liability"] * 1,
    "umbrella": ["liability"],
}
CLAIM_STATUSES = ["open", "triaged", "assessed", "settled", "denied"]
DOC_TYPES      = ["police_report", "estimate", "photo_caption", "medical", "email"]

def gen_policies(n: int = 5000) -> list[dict]:
    out: list[dict] = []
    for i in range(n):
        product = random.choice(PRODUCT_LINES)
        eff = fake.date_between(start_date="-3y", end_date="-1d")
        exp = eff + timedelta(days=365)
        status = "active" if random.random() < 0.9 else "lapsed"
        coverage = {
            "bodily_injury_per_person": random.choice([25000, 50000, 100000, 250000]),
            "bodily_injury_per_accident": random.choice([50000, 100000, 300000, 500000]),
            "property_damage": random.choice([25000, 50000, 100000]),
            "collision_deductible": random.choice([250, 500, 1000]) if product == "auto" else None,
            "comprehensive_deductible": random.choice([250, 500, 1000]) if product == "auto" else None,
            "dwelling_limit": random.choice([200000, 350000, 500000, 750000]) if product == "home" else None,
            "umbrella_limit": random.choice([1000000, 2000000, 5000000]) if product == "umbrella" else None,
        }
        out.append({
            "PolicyId": str(uuid.uuid4()),
            "PolicyNumber": f"POL-{1_000_000 + i}",
            "ProductLine": product,
            "EffectiveDate": eff,
            "ExpirationDate": exp,
            "PremiumAnnual": round(random.uniform(400, 4800), 2),
            "CoverageJson": json.dumps({k: v for k, v in coverage.items() if v is not None}),
            "Status": status,
        })
    return out

def gen_parties(n: int = 8000) -> list[dict]:
    out: list[dict] = []
    for _ in range(n):
        role = random.choices(["insured", "claimant", "witness", "provider"], weights=[0.55, 0.30, 0.10, 0.05])[0]
        full = fake.name()
        addr = {
            "street": fake.street_address(),
            "city":   fake.city(),
            "state":  random.choice(US_STATES),
            "zip":    fake.postcode(),
        }
        out.append({
            "PartyId": str(uuid.uuid4()),
            "Role": role,
            "FullName": full,
            "Email": fake.email(),
            "Phone": fake.numerify("###-###-####"),
            "AddressJson": json.dumps(addr),
            "DOB": fake.date_of_birth(minimum_age=18, maximum_age=85),
        })
    return out

POLICE_TEMPLATE = (
    "Incident report #{report_no}. On {date_str} at approximately {time_str}, "
    "officer {officer} responded to a report of {loss_phrase} at {location}. "
    "Driver of vehicle 1, {driver1}, stated that {narrative1}. Driver of vehicle 2, {driver2}, "
    "stated that {narrative2}. Estimated damage to vehicle 1: ${dmg1}. "
    "No injuries reported. {weather}"
)
ESTIMATE_TEMPLATE = (
    "Repair estimate for {plate}. Customer: {customer}. Shop: {shop}.\n"
    "Line items:\n- {part1}: ${cost1}\n- {part2}: ${cost2}\n- {part3}: ${cost3}\n"
    "Labor: {hours} hrs @ $120/hr = ${labor}.\nSubtotal: ${subtotal}\nTax: ${tax}\n"
    "TOTAL: ${total}\nNotes: {notes}"
)
EMAIL_TEMPLATE = (
    "From: {sender}\nTo: claims@contoso-insurance.example\nSubject: Claim {claim_no} update\n\n"
    "Hi team,\n\n{body}\n\nThanks,\n{sender_first}"
)
MEDICAL_TEMPLATE = (
    "Provider: {provider}. Patient: {patient}. DOS: {dos}. "
    "Chief complaint: {complaint}. Assessment: {assessment}. "
    "Billed services: {service} (${charge}). Plan: {plan}."
)
PHOTO_TEMPLATE = (
    "Photo {n} of {total}. Description: {desc}. Taken {when}. "
    "Visible damage: {damage}."
)

def _police_text(loss_dt: datetime) -> str:
    return POLICE_TEMPLATE.format(
        report_no=fake.numerify("###-####"),
        date_str=loss_dt.strftime("%Y-%m-%d"),
        time_str=loss_dt.strftime("%H:%M"),
        officer=fake.name(),
        loss_phrase=random.choice(["a two-vehicle collision", "a single-vehicle accident", "a hit-and-run"]),
        location=fake.street_address(),
        driver1=fake.name(),
        narrative1=random.choice(["the other vehicle failed to yield", "they were rear-ended at a stop sign", "the road was wet"]),
        driver2=fake.name(),
        narrative2=random.choice(["they had the right of way", "they did not see the other vehicle", "they were turning left"]),
        dmg1=random.randint(800, 18000),
        weather=random.choice(["Clear skies.", "Light rain at time of incident.", "Heavy fog reported."]),
    )

def _estimate_text() -> str:
    cost1, cost2, cost3 = (random.randint(150, 2200) for _ in range(3))
    hours = round(random.uniform(2, 14), 1)
    labor = round(hours * 120, 2)
    subtotal = cost1 + cost2 + cost3 + labor
    tax = round(subtotal * 0.0825, 2)
    return ESTIMATE_TEMPLATE.format(
        plate=fake.license_plate(),
        customer=fake.name(),
        shop=fake.company() + " Auto Body",
        part1=random.choice(["Front bumper assembly", "Hood panel", "Driver door"]),
        cost1=cost1,
        part2=random.choice(["Headlamp assembly L", "Fender R", "Quarter panel L"]),
        cost2=cost2,
        part3=random.choice(["Paint and prep", "Wheel R", "Airbag module"]),
        cost3=cost3,
        hours=hours, labor=labor,
        subtotal=subtotal, tax=tax, total=round(subtotal + tax, 2),
        notes=random.choice(["OEM parts requested.", "Aftermarket acceptable.", "Customer requests rental coverage."]),
    )

def _email_text(claim_no: str) -> str:
    sender = fake.name()
    return EMAIL_TEMPLATE.format(
        sender=f"{sender} <{sender.split()[0].lower()}@example.com>",
        claim_no=claim_no,
        body=random.choice([
            "Following up on the inspection scheduled for next Tuesday.",
            "Please find attached the additional photos you requested.",
            "Insured would like to know status of the rental authorization.",
        ]),
        sender_first=sender.split()[0],
    )

def _medical_text() -> str:
    return MEDICAL_TEMPLATE.format(
        provider=fake.company() + " Medical Group",
        patient=fake.name(),
        dos=fake.date_between(start_date="-90d").isoformat(),
        complaint=random.choice(["neck pain post-MVA", "lower back stiffness", "headache and dizziness"]),
        assessment=random.choice(["cervical strain", "lumbar sprain", "post-concussive symptoms"]),
        service=random.choice(["Office visit (99213)", "MRI cervical (72141)", "Physical therapy (97110)"]),
        charge=random.randint(180, 2400),
        plan=random.choice(["Continue PT 2x/week.", "Recheck in 14 days.", "Refer to ortho."]),
    )

def _photo_text(claim_no: str) -> str:
    n = random.randint(1, 6)
    return PHOTO_TEMPLATE.format(
        n=n, total=n + random.randint(0, 4),
        desc=random.choice(["Driver-side damage", "Rear bumper", "Interior airbag deployment", "Roof leak interior"]),
        when=fake.date_time_this_year().strftime("%Y-%m-%d %H:%M"),
        damage=random.choice(["Crushed front quarter, hood buckled", "Cracked tail lamp", "Water staining on ceiling"]),
    )

# ---- Fraud rings ---------------------------------------------------------

def inject_fraud_rings(parties: list[dict], n_rings: int = 30, ring_size: int = 4) -> list[str]:
    """
    Overwrite shared phone/address across `ring_size` parties per ring, so link
    analysis can later surface them. Returns the set of "ring" party IDs.
    """
    ring_party_ids: list[str] = []
    for _ in range(n_rings):
        shared_phone = fake.numerify("###-###-####")
        shared_addr  = json.dumps({
            "street": fake.street_address(),
            "city":   fake.city(),
            "state":  random.choice(US_STATES),
            "zip":    fake.postcode(),
        })
        members = random.sample(parties, ring_size)
        for p in members:
            p["Phone"] = shared_phone
            p["AddressJson"] = shared_addr
            ring_party_ids.append(p["PartyId"])
    return ring_party_ids

# ---- Main ----------------------------------------------------------------

def main() -> int:
    conn = _connect()
    try:
        apply_schema(conn)
        if RESEED:
            truncate_all(conn)
        cur = conn.cursor()

        # PolicyRule -----------------------------------------------------
        rules = [
            ("FAIR-001", "fair_claims",   "Acknowledge FNOL within 15 calendar days.",
                {"max_ack_days": 15}, "1.0"),
            ("FAIR-002", "fair_claims",   "Communicate coverage decision within 40 days of completed proof of loss.",
                {"max_decision_days": 40}, "1.0"),
            ("FAIR-003", "fair_claims",   "Provide written denial with statutory citation.",
                {"requires": ["citation", "appeal_rights"]}, "1.0"),
            ("LIMIT-001", "coverage_limit", "Settlement shall not exceed policy property damage limit.",
                {"check": "settlement <= coverage.property_damage"}, "1.0"),
            ("LIMIT-002", "coverage_limit", "Settlement shall not exceed bodily injury per-person limit.",
                {"check": "settlement <= coverage.bodily_injury_per_person"}, "1.0"),
            ("LIMIT-003", "coverage_limit", "Auto comprehensive subject to deductible.",
                {"apply": "deductible.comprehensive"}, "1.0"),
            ("ANTI-001",  "anti_discrim",  "Decision rationale must not reference protected class attributes.",
                {"forbid_terms": ["age", "race", "national origin", "religion", "gender", "zip code"]}, "1.0"),
            ("ANTI-002",  "anti_discrim",  "Decision must not denominate party by surname alone.",
                {"forbid_pattern": "surname_only"}, "1.0"),
            ("STATE-TX-001", "state_reg", "TX prompt-pay: settle within 60 days of acceptance.",
                {"state": "TX", "max_settle_days": 60}, "1.0"),
            ("STATE-CA-001", "state_reg", "CA: written acknowledgement within 15 days.",
                {"state": "CA", "max_ack_days": 15}, "1.0"),
            ("STATE-FL-001", "state_reg", "FL: pay or deny within 90 days after notice of loss.",
                {"state": "FL", "max_decision_days": 90}, "1.0"),
            ("SIU-001",   "fair_claims",   "Refer to SIU when fraud score >= 0.70.",
                {"siu_threshold": 0.70}, "1.0"),
            ("DOC-001",   "fair_claims",   "Require police report for auto collisions with damage > $5,000.",
                {"trigger": {"loss_type": "auto_collision", "damage_gt": 5000}, "require": "police_report"}, "1.0"),
            ("DOC-002",   "fair_claims",   "Require itemized estimate for any property damage claim.",
                {"require": "estimate"}, "1.0"),
            ("RES-001",   "coverage_limit", "Reserve must be set within 5 business days of triage.",
                {"max_reserve_days": 5}, "1.0"),
            ("SUB-001",   "fair_claims",   "Pursue subrogation when third-party fault probability > 0.6.",
                {"sub_threshold": 0.6}, "1.0"),
            ("AI-001",    "fair_claims",   "All AI decisions require human approval before payment.",
                {"requires_human": True, "before": "payment"}, "1.0"),
            ("AI-002",    "fair_claims",   "Every AI decision must record model name, version, and rationale.",
                {"requires": ["model", "version", "rationale"]}, "1.0"),
            ("AI-003",    "fair_claims",   "Settlement recommendations must cite supporting documents by id.",
                {"requires": "document_citations"}, "1.0"),
            ("DENY-001",  "fair_claims",   "Denials must enumerate every coverage clause considered.",
                {"requires": "clauses_considered"}, "1.0"),
            ("FRAUD-001", "fair_claims",   "Shared identifiers across >2 unrelated claims warrants link review.",
                {"shared_id_threshold": 2}, "1.0"),
            ("FRAUD-002", "fair_claims",   "Late-night loss within 7 days of policy bind raises severity.",
                {"window_days": 7, "night_hours": [22, 23, 0, 1, 2, 3, 4]}, "1.0"),
            ("EST-001",   "coverage_limit", "Estimate variance > 35% vs. comparable repairs requires SIU review.",
                {"variance_threshold": 0.35}, "1.0"),
            ("MED-001",   "coverage_limit", "Medical bill review required for charges > $2,500.",
                {"med_review_threshold": 2500}, "1.0"),
            ("AUDIT-001", "fair_claims",   "Audit events are append-only; no modification permitted.",
                {"append_only": True}, "1.0"),
        ]
        rule_id_map: dict[str, str] = {}
        for code, cat, desc, pred, ver in rules:
            rid = str(uuid.uuid4())
            rule_id_map[code] = rid
            cur.execute(
                "INSERT INTO dbo.PolicyRule (RuleId, RuleCode, Category, Description, PredicateJson, Version, IsActive) VALUES (?,?,?,?,?,?,1)",
                rid, code, cat, desc, json.dumps(pred), ver,
            )
        print(f"[seed] Inserted {len(rules)} policy rules")

        # Policies -------------------------------------------------------
        policies = gen_policies(5000)
        cur.fast_executemany = True
        cur.executemany(
            "INSERT INTO dbo.Policy (PolicyId, PolicyNumber, ProductLine, EffectiveDate, ExpirationDate, PremiumAnnual, CoverageJson, Status) VALUES (?,?,?,?,?,?,?,?)",
            [(p["PolicyId"], p["PolicyNumber"], p["ProductLine"], p["EffectiveDate"], p["ExpirationDate"],
              p["PremiumAnnual"], p["CoverageJson"], p["Status"]) for p in policies],
        )
        print(f"[seed] Inserted {len(policies)} policies")

        # Parties + fraud rings -----------------------------------------
        parties = gen_parties(8000)
        ring_party_ids = inject_fraud_rings(parties, n_rings=30, ring_size=4)
        cur.executemany(
            "INSERT INTO dbo.Party (PartyId, Role, FullName, Email, Phone, AddressJson, DOB) VALUES (?,?,?,?,?,?,?)",
            [(p["PartyId"], p["Role"], p["FullName"], p["Email"], p["Phone"], p["AddressJson"], p["DOB"]) for p in parties],
        )
        print(f"[seed] Inserted {len(parties)} parties (with {len(ring_party_ids)} in fraud rings)")

        # Claims ---------------------------------------------------------
        active_policies = [p for p in policies if p["Status"] == "active"]
        n_claims = 2000
        claims: list[dict] = []
        for i in range(n_claims):
            pol = random.choice(active_policies)
            loss_dt = fake.date_time_between(start_date="-24M", end_date="-1d", tzinfo=timezone.utc)
            loss_type = random.choice(LOSS_TYPES_BY_PRODUCT[pol["ProductLine"]])
            status = random.choices(CLAIM_STATUSES, weights=[0.15, 0.20, 0.20, 0.40, 0.05])[0]
            reported = round(random.lognormvariate(8.2, 0.6), 2)  # ~$3.6k median
            reserve  = round(reported * random.uniform(0.85, 1.15), 2) if status != "open" else None
            settled  = round(reserve * random.uniform(0.7, 1.0), 2) if status == "settled" and reserve else None
            claims.append({
                "ClaimId": str(uuid.uuid4()),
                "PolicyId": pol["PolicyId"],
                "ClaimNumber": f"CLM-{100_001 + i}",
                "LossDateTime": loss_dt.replace(tzinfo=None),
                "LossType": loss_type,
                "Status": status,
                "ReportedAmount": reported,
                "ReserveAmount":  reserve,
                "SettledAmount":  settled,
                "TriageDecisionJson": None,
                "AssignedAdjuster": random.choice(["alex.morgan@contoso.example", "priya.patel@contoso.example", "sam.lee@contoso.example"]),
            })
        cur.executemany(
            "INSERT INTO dbo.Claim (ClaimId, PolicyId, ClaimNumber, LossDateTime, LossType, Status, ReportedAmount, ReserveAmount, SettledAmount, TriageDecisionJson, AssignedAdjuster) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(c["ClaimId"], c["PolicyId"], c["ClaimNumber"], c["LossDateTime"], c["LossType"], c["Status"],
              c["ReportedAmount"], c["ReserveAmount"], c["SettledAmount"], c["TriageDecisionJson"], c["AssignedAdjuster"]) for c in claims],
        )
        print(f"[seed] Inserted {len(claims)} claims")

        # Demo claims (CLM-100001..100005) – ensure they exist as the deck-aligned demo
        # They're already the first 5 claims by insertion order — we just leave them as-is.

        # Documents ------------------------------------------------------
        docs: list[tuple] = []
        for c in claims:
            n_docs = random.choices([2, 3, 4], weights=[0.5, 0.35, 0.15])[0]
            for _ in range(n_docs):
                dtype = random.choice(DOC_TYPES)
                if dtype == "police_report":
                    text = _police_text(c["LossDateTime"])
                elif dtype == "estimate":
                    text = _estimate_text()
                elif dtype == "email":
                    text = _email_text(c["ClaimNumber"])
                elif dtype == "medical":
                    text = _medical_text()
                else:
                    text = _photo_text(c["ClaimNumber"])
                docs.append((str(uuid.uuid4()), c["ClaimId"], dtype, dtype.replace("_", " ").title(), text, None))
        cur.executemany(
            "INSERT INTO dbo.Document (DocumentId, ClaimId, DocType, Title, RawText, ExtractedJson) VALUES (?,?,?,?,?,?)",
            docs,
        )
        print(f"[seed] Inserted {len(docs)} documents")

        # Fraud signals --------------------------------------------------
        # Curate 150-claim fraud-positive subset
        fraud_claims = random.sample(claims, 150)
        signals: list[tuple] = []
        for c in fraud_claims:
            patterns = random.sample([
                ("link_analysis", round(random.uniform(0.72, 0.95), 4),
                 {"reason": "Shared phone/address across >=3 unrelated insureds", "rule": "FRAUD-001"}),
                ("rule",          round(random.uniform(0.65, 0.90), 4),
                 {"reason": "Loss occurred at 02:14, within 7d of policy bind", "rule": "FRAUD-002"}),
                ("model",         round(random.uniform(0.60, 0.85), 4),
                 {"reason": "Estimate variance 42% above comparable repairs", "rule": "EST-001"}),
            ], k=random.choice([1, 2]))
            for stype, score, rj in patterns:
                signals.append((str(uuid.uuid4()), c["ClaimId"], stype, score, json.dumps(rj)))
        # Also seed low-score signals on non-fraud claims so the dashboard isn't sparse
        for c in random.sample([c for c in claims if c not in fraud_claims], 700):
            signals.append((str(uuid.uuid4()), c["ClaimId"], "rule", round(random.uniform(0.05, 0.35), 4),
                            json.dumps({"reason": "Baseline rules — no anomalies", "rule": "FRAUD-001"})))
        cur.executemany(
            "INSERT INTO dbo.FraudSignal (SignalId, ClaimId, SignalType, Score, RationaleJson) VALUES (?,?,?,?,?)",
            signals,
        )
        print(f"[seed] Inserted {len(signals)} fraud signals ({len(fraud_claims)} fraud-positive claims)")

        # Pre-seeded agent decisions on the first 3 claims (so demo opens "completed" state)
        precooked: list[tuple] = []
        precooked_audit: list[tuple] = []
        for c in claims[:3]:
            did = str(uuid.uuid4())
            payload = {
                "rationale": "Coverage confirmed for collision; deductible $500 applied.",
                "model": "gpt-4o", "version": "2024-08-06",
                "document_citations": [],
            }
            precooked.append((did, c["ClaimId"], "TriageCoverageAgent", "coverage", json.dumps(payload), "approved"))
            precooked_audit.append((
                str(uuid.uuid4()), c["ClaimId"], did, rule_id_map["AI-002"],
                "agent", "TriageCoverageAgent", "coverage.evaluate", "pass",
                json.dumps({"rule": "AI-002", "version": "1.0", "note": "Decision metadata present."}),
                f"corr-{c['ClaimNumber']}",
            ))
            did2 = str(uuid.uuid4())
            sp = {
                "rationale": "Three estimates received; median used.",
                "line_items": [{"part": "Front bumper", "cost": 1850}, {"part": "Hood", "cost": 1200}, {"labor_hrs": 8}],
                "settlement_amount": 4250.00, "currency": "USD",
                "subrogation": False, "model": "gpt-4o", "version": "2024-08-06",
            }
            precooked.append((did2, c["ClaimId"], "AssessmentSettlementAgent", "settlement", json.dumps(sp), "approved"))
            precooked_audit.append((
                str(uuid.uuid4()), c["ClaimId"], did2, rule_id_map["LIMIT-001"],
                "agent", "GuardrailsAgent", "settlement.guardrail", "pass",
                json.dumps({"rule": "LIMIT-001", "version": "1.0", "settlement": 4250.00, "limit": 50000}),
                f"corr-{c['ClaimNumber']}",
            ))
        cur.executemany(
            "INSERT INTO dbo.AgentDecision (DecisionId, ClaimId, AgentName, DecisionType, PayloadJson, Status) VALUES (?,?,?,?,?,?)",
            precooked,
        )

        # Backfilled audit events ---------------------------------------
        # 5,000 historical FNOL acknowledgements + 5,000 misc agent passes
        audit_rows: list[tuple] = list(precooked_audit)
        adjusters = ["alex.morgan@contoso.example", "priya.patel@contoso.example", "sam.lee@contoso.example"]
        for c in random.sample(claims, min(5000, len(claims))):
            audit_rows.append((
                str(uuid.uuid4()), c["ClaimId"], None, rule_id_map["FAIR-001"],
                "human", random.choice(adjusters), "fnol.acknowledge", "pass",
                json.dumps({"rule": "FAIR-001", "version": "1.0", "within_days": random.randint(1, 14)}),
                f"corr-{c['ClaimNumber']}",
            ))
        for c in random.sample(claims, min(5000, len(claims))):
            audit_rows.append((
                str(uuid.uuid4()), c["ClaimId"], None, rule_id_map["AI-002"],
                "agent", random.choice(["FnolDocumentAgent", "TriageCoverageAgent", "AssessmentSettlementAgent"]),
                "agent.run", "pass",
                json.dumps({"rule": "AI-002", "version": "1.0"}),
                f"corr-{c['ClaimNumber']}",
            ))
        cur.executemany(
            "INSERT INTO dbo.AuditEvent (EventId, ClaimId, DecisionId, RuleId, Actor, ActorName, Action, Outcome, RationaleJson, CorrelationId) VALUES (?,?,?,?,?,?,?,?,?,?)",
            audit_rows,
        )
        print(f"[seed] Inserted {len(audit_rows)} audit events")

        conn.commit()
        print("[seed] DONE.")
        return 0
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())
