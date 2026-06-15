"""Generate telematics blobs and Cosmos records for auto policies."""
from __future__ import annotations

import argparse
import json
import os
import random
import struct
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pyodbc
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from faker import Faker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / ".seed_state" / "gen_sql_output.json"
TELEMATICS_STATE_PATH = SCRIPT_DIR / ".seed_state" / "telematics_summary.json"
EVENT_TYPES = ["trip_start", "gps", "hard_accel", "hard_brake", "crash_g", "trip_end"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blob-account-name", default=os.getenv("BLOB_ACCOUNT_NAME"))
    parser.add_argument("--cosmos-endpoint", default=os.getenv("COSMOS_ENDPOINT"))
    parser.add_argument("--cosmos-database", default=os.getenv("COSMOS_DATABASE"))
    parser.add_argument("--sql-server-fqdn", default=os.getenv("SQL_SERVER_FQDN"))
    parser.add_argument("--sql-database-name", default=os.getenv("SQL_DATABASE_NAME"))
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    for field in ("blob_account_name", "cosmos_endpoint", "cosmos_database"):
        if not getattr(args, field):
            parser.error(f"{field.replace('_', '-')} is required via args or env vars.")
    return args


def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(exclude_interactive_browser_credential=False)


def _blob_service(account_name: str) -> BlobServiceClient:
    return BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=_credential())


def _cosmos_container(args: argparse.Namespace):
    client = CosmosClient(args.cosmos_endpoint, credential=_credential())
    database = client.create_database_if_not_exists(args.cosmos_database)
    return database.create_container_if_not_exists(id="telematics", partition_key=PartitionKey(path="/policyNumber"))


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Run gen_sql.py first; manifest not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_windows(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    windows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in manifest["claims"]:
        if claim["loss_type"].startswith("auto"):
            windows[claim["policy_number"]].append(claim)
    return windows


def _build_event(policy_number: str, timestamp: datetime, event_type: str, claim: dict[str, Any] | None = None) -> dict[str, Any]:
    lat = round(float(RNG.uniform(29.0, 47.0)), 6)
    lon = round(float(RNG.uniform(-122.0, -73.0)), 6)
    event = {
        "id": f"{policy_number}-{event_type}-{timestamp.strftime('%Y%m%d%H%M%S')}-{int(RNG.integers(1000, 9999))}",
        "source": "seed_v2",
        "policyNumber": policy_number,
        "eventType": event_type,
        "eventUtc": timestamp.isoformat(),
        "lat": lat,
        "lon": lon,
        "g_force": round(float(RNG.uniform(0.1, 2.6)), 3) if event_type == "crash_g" else None,
        "hardness": round(float(RNG.uniform(0.1, 1.0)), 3) if event_type in {"hard_brake", "hard_accel"} else None,
        "claimNumber": claim["claim_number"] if claim else None,
        "state": claim["state"] if claim else None,
    }
    return event


def _generate_day_events(policy_number: str, day: datetime, policy_claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = datetime.combine(day.date(), datetime.min.time(), tzinfo=UTC)
    events = [
        _build_event(policy_number, base + timedelta(hours=7, minutes=int(RNG.integers(0, 30))), "trip_start"),
        _build_event(policy_number, base + timedelta(hours=7, minutes=12), "gps"),
        _build_event(policy_number, base + timedelta(hours=7, minutes=29), "trip_end"),
    ]
    if RNG.random() < 0.35:
        events.insert(2, _build_event(policy_number, base + timedelta(hours=7, minutes=20), random.choice(["hard_accel", "hard_brake"])))
    for claim in policy_claims:
        loss_dt = datetime.fromisoformat(claim["loss_datetime"]).replace(tzinfo=UTC)
        if loss_dt.date() != day.date():
            continue
        hints = claim.get("telematics_hints", {})
        if "hard_brake" in hints:
            events.append(_build_event(policy_number, loss_dt + timedelta(seconds=int(hints["hard_brake"])), "hard_brake", claim))
        if "crash_g" in hints:
            events.append(_build_event(policy_number, loss_dt + timedelta(seconds=int(hints["crash_g"])), "crash_g", claim))
        if hints.get("normal"):
            events.append(_build_event(policy_number, loss_dt - timedelta(seconds=15), "gps", claim))
    events.sort(key=lambda item: item["eventUtc"])
    return events


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=16), retry=retry_if_exception_type(Exception), reraise=True)
def _upload_blob(container, blob_name: str, payload: str) -> None:
    container.upload_blob(name=blob_name, data=payload.encode("utf-8"), overwrite=True)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=16), retry=retry_if_exception_type(Exception), reraise=True)
def _upsert_batch(container, docs: Iterable[dict[str, Any]]) -> None:
    for doc in docs:
        container.upsert_item(doc)


def _chunked(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(items), size):
        yield items[index:index + size]


def _clear_blob_prefixes(container, policies: list[str]) -> int:
    deleted = 0
    for policy_number in policies:
        for blob in container.list_blobs(name_starts_with=f"{policy_number}/"):
            container.delete_blob(blob.name)
            deleted += 1
    return deleted


def _clear_cosmos(container) -> int:
    deleted = 0
    query = "SELECT c.id, c.policyNumber FROM c WHERE c.source = 'seed_v2'"
    for item in container.query_items(query=query, enable_cross_partition_query=True):
        container.delete_item(item=item["id"], partition_key=item["policyNumber"])
        deleted += 1
    return deleted


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_telematics] Deterministic seed={SEED}")
    manifest = _load_manifest(args.manifest_path)
    auto_policies = [policy for policy in manifest["policies"] if policy["product_line"] == "auto"][:800]
    claim_windows = _claim_windows(manifest)
    blob_container = _blob_service(args.blob_account_name).get_container_client("telematics-raw")
    blob_container.create_container(exist_ok=True)
    cosmos_container = _cosmos_container(args)
    deleted_blobs = _clear_blob_prefixes(blob_container, [policy["policy_number"] for policy in auto_policies])
    deleted_docs = _clear_cosmos(cosmos_container)
    print(f"[gen_telematics] Cleared {deleted_blobs} blobs and {deleted_docs} Cosmos items")

    all_docs: list[dict[str, Any]] = []
    files_written = 0
    claim_event_counts: dict[str, int] = defaultdict(int)
    for policy in auto_policies:
        policy_number = policy["policy_number"]
        for day_offset in range(90):
            day = datetime.now(UTC) - timedelta(days=89 - day_offset)
            events = _generate_day_events(policy_number, day, claim_windows.get(policy_number, []))
            for event in events:
                if event["claimNumber"]:
                    claim_event_counts[event["claimNumber"]] += 1
            blob_name = f"{policy_number}/{day:%Y-%m-%d}.jsonl"
            payload = "
".join(json.dumps(event, sort_keys=True) for event in events)
            _upload_blob(blob_container, blob_name, payload)
            files_written += 1
            all_docs.extend(events)
        if files_written % 1800 == 0:
            print(f"[gen_telematics] Wrote {files_written} JSONL blobs ...")

    for batch in _chunked(all_docs, 100):
        _upsert_batch(cosmos_container, batch)
    TELEMATICS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TELEMATICS_STATE_PATH.write_text(json.dumps({"claim_event_counts": claim_event_counts, "event_count": len(all_docs)}, indent=2), encoding="utf-8")
    summary = {"generator": "gen_telematics", "policies": len(auto_policies), "blob_files": files_written, "events": len(all_docs)}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
