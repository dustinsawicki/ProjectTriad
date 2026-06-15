"""Replay the last 24 hours of telematics events to Event Hub."""
from __future__ import annotations

import argparse
import json
import os
import random
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
from azure.eventhub import EventData, EventHubProducerClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blob-account-name", default=os.getenv("BLOB_ACCOUNT_NAME"))
    parser.add_argument("--event-hub-namespace-fqdn", default=os.getenv("EVENT_HUB_NAMESPACE_FQDN"))
    parser.add_argument("--event-hub-name", default="telematics-stream")
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    if not args.blob_account_name or not args.event_hub_namespace_fqdn:
        parser.error("BLOB_ACCOUNT_NAME and EVENT_HUB_NAMESPACE_FQDN are required.")
    return args


def _blob_service(account_name: str) -> BlobServiceClient:
    return BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[replay_telematics] Deterministic seed={SEED}")
    container = _blob_service(args.blob_account_name).get_container_client("telematics-raw")
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    events: list[dict[str, object]] = []
    for blob in container.list_blobs():
        if not blob.name.endswith(".jsonl"):
            continue
        payload = container.download_blob(blob.name).readall().decode("utf-8")
        for line in payload.splitlines():
            item = json.loads(line)
            event_time = datetime.fromisoformat(item["eventUtc"])
            if event_time >= cutoff:
                events.append(item)
    producer = EventHubProducerClient(fully_qualified_namespace=args.event_hub_namespace_fqdn, eventhub_name=args.event_hub_name, credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))
    sent = 0
    with producer:
        batch = producer.create_batch()
        batch_count = 0
        for event in events:
            event_data = EventData(json.dumps(event))
            try:
                batch.add(event_data)
                batch_count += 1
            except ValueError:
                producer.send_batch(batch)
                sent += batch_count
                batch = producer.create_batch()
                batch.add(event_data)
                batch_count = 1
        if batch_count > 0:
            producer.send_batch(batch)
            sent += batch_count
    summary = {"generator": "replay_telematics", "events_replayed": sent}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
