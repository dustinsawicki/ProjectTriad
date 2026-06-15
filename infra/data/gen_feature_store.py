"""Build claim and party feature rollups into Cosmos DB."""
from __future__ import annotations

import argparse
import json
import os
import random
import struct
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pyodbc
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / ".seed_state" / "gen_sql_output.json"
TELEMATICS_STATE_PATH = SCRIPT_DIR / ".seed_state" / "telematics_summary.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cosmos-endpoint", default=os.getenv("COSMOS_ENDPOINT"))
    parser.add_argument("--cosmos-database", default=os.getenv("COSMOS_DATABASE"))
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--telematics-state-path", type=Path, default=TELEMATICS_STATE_PATH)
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    if not args.cosmos_endpoint or not args.cosmos_database:
        parser.error("COSMOS_ENDPOINT and COSMOS_DATABASE are required.")
    return args


def _cosmos_container(args: argparse.Namespace):
    client = CosmosClient(args.cosmos_endpoint, credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))
    database = client.create_database_if_not_exists(id=args.cosmos_database)
    return database.create_container_if_not_exists(id="feature_store", partition_key=PartitionKey(path="/key"))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required state file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _clear_existing(container) -> int:
    deleted = 0
    for item in container.query_items("SELECT c.id, c.key FROM c WHERE c.source = 'seed_v2'", enable_cross_partition_query=True):
        container.delete_item(item=item["id"], partition_key=item["key"])
        deleted += 1
    return deleted


def _weather_severity(state: str, claim_number: str) -> float:
    seed_value = sum(ord(char) for char in f"{state}-{claim_number}-{SEED}")
    return round((seed_value % 95) / 10.0, 2)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_feature_store] Deterministic seed={SEED}")
    manifest = _load_json(args.manifest_path)
    telematics_state = _load_json(args.telematics_state_path) if args.telematics_state_path.exists() else {"claim_event_counts": {}}
    claim_event_counts = telematics_state.get("claim_event_counts", {})
    doc_count_by_claim = Counter(document["claim_number"] for document in manifest["documents"])
    photo_count_by_claim = {claim["claim_number"]: claim["photo_count"] for claim in manifest["claims"]}
    claims_by_loss = defaultdict(list)
    for claim in manifest["claims"]:
        claims_by_loss[claim["loss_type"]].append(claim)

    claim_features: list[dict[str, Any]] = []
    for claim in manifest["claims"]:
        historical_similar_count = max(len(claims_by_loss[claim["loss_type"]]) - 1, 0)
        key = f"claim:{claim['claim_id']}"
        claim_features.append(
            {
                "id": key,
                "key": key,
                "source": "seed_v2",
                "entityType": "claim",
                "claimNumber": claim["claim_number"],
                "doc_count": doc_count_by_claim[claim["claim_number"]],
                "photo_count": photo_count_by_claim.get(claim["claim_number"], 0),
                "telematics_event_count_loss_window": int(claim_event_counts.get(claim["claim_number"], 0)),
                "weather_severity": _weather_severity(claim["state"], claim["claim_number"]),
                "historical_similar_count": historical_similar_count,
                "computed_utc": datetime.now(UTC).isoformat(),
            }
        )

    party_claim_counts = defaultdict(int)
    party_doc_counts = defaultdict(int)
    party_photo_counts = defaultdict(int)
    party_states: dict[str, str] = {}
    for claim in manifest["claims"]:
        for party_id in claim["party_ids"][:2]:
            party_claim_counts[party_id] += 1
            party_doc_counts[party_id] += doc_count_by_claim[claim["claim_number"]]
            party_photo_counts[party_id] += photo_count_by_claim.get(claim["claim_number"], 0)
            party_states.setdefault(party_id, claim["state"])

    party_features: list[dict[str, Any]] = []
    for entry in manifest["ring_parties"][:3000]:
        party_id = entry["party_id"]
        key = f"party:{party_id}"
        party_features.append(
            {
                "id": key,
                "key": key,
                "source": "seed_v2",
                "entityType": "party",
                "partyId": party_id,
                "doc_count": int(party_doc_counts.get(party_id, 0)),
                "photo_count": int(party_photo_counts.get(party_id, 0)),
                "telematics_event_count_loss_window": 0,
                "weather_severity": _weather_severity(party_states.get(party_id, entry["state"]), party_id[-8:]),
                "historical_similar_count": int(party_claim_counts.get(party_id, 0)),
                "computed_utc": datetime.now(UTC).isoformat(),
            }
        )
    if len(party_features) < 3000:
        extra_index = 0
        while len(party_features) < 3000:
            placeholder = f"synthetic-party-{extra_index:04d}"
            key = f"party:{placeholder}"
            party_features.append(
                {
                    "id": key,
                    "key": key,
                    "source": "seed_v2",
                    "entityType": "party",
                    "partyId": placeholder,
                    "doc_count": int(extra_index % 4),
                    "photo_count": int(extra_index % 3),
                    "telematics_event_count_loss_window": 0,
                    "weather_severity": round(float(RNG.uniform(0.0, 9.5)), 2),
                    "historical_similar_count": int(extra_index % 5),
                    "computed_utc": datetime.now(UTC).isoformat(),
                }
            )
            extra_index += 1

    container = _cosmos_container(args)
    deleted = _clear_existing(container)
    print(f"[gen_feature_store] Cleared {deleted} existing feature rows")
    for record in claim_features + party_features:
        container.upsert_item(record)
    summary = {"generator": "gen_feature_store", "claim_features": len(claim_features), "party_features": len(party_features), "total": len(claim_features) + len(party_features)}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
