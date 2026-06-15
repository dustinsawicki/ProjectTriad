"""Generate historical markdown corpus and upload it to Blob Storage."""
from __future__ import annotations

import argparse
import json
import os
import random
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
from azure.core.exceptions import ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
LOSS_TYPES = ["auto_collision", "auto_comp", "home_property", "liability"]
US_STATES = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "MN", "WA", "AZ"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blob-account-name", default=os.getenv("BLOB_ACCOUNT_NAME"))
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    if not args.blob_account_name:
        parser.error("BLOB_ACCOUNT_NAME is required.")
    return args


def _blob_service(account_name: str) -> BlobServiceClient:
    return BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))


def _clear_prefix(container, prefix: str) -> int:
    deleted = 0
    for blob in container.list_blobs(name_starts_with=prefix):
        container.delete_blob(blob.name)
        deleted += 1
    return deleted


def _front_matter(kind: str, title: str, loss_type: str, state: str, settled_amount: float, settled_date: date) -> str:
    return (
        "---\n"
        f"kind: {kind}\n"
        f"title: {title}\n"
        f"loss_type: {loss_type}\n"
        f"state: {state}\n"
        f"settled_amount: {settled_amount:.2f}\n"
        f"settled_date: {settled_date.isoformat()}\n"
        "---\n\n"
    )


def _claim_markdown(index: int) -> str:
    loss_type = LOSS_TYPES[index % len(LOSS_TYPES)]
    state = US_STATES[index % len(US_STATES)]
    settled_date = (datetime.now(UTC) - timedelta(days=30 + index)).date()
    amount = round(float(RNG.uniform(1200, 18500)), 2)
    title = f"Historical claim summary {index:03d}"
    body = (
        f"Loss narrative: {fake.paragraph(nb_sentences=5)}\n\n"
        f"Key terms: {loss_type}, reserve review, claimant contact, settlement memo, {state}.\n\n"
        f"Outcome: settled after review with supporting estimate and documented rationale."
    )
    return _front_matter("historical_claim", title, loss_type, state, amount, settled_date) + body


def _endorsement_markdown(index: int) -> str:
    state = US_STATES[index % len(US_STATES)]
    settled_date = (datetime.now(UTC) - timedelta(days=300 + index)).date()
    title = f"Policy endorsement {index:03d}"
    body = f"Coverage endorsement for {state}. Adds detail on deductible, water backup, rental reimbursement, and appraisal language."
    return _front_matter("policy_endorsement", title, "home_property", state, 0.0, settled_date) + body


def _bulletin_markdown(state: str, index: int) -> str:
    settled_date = (datetime.now(UTC) - timedelta(days=120 + index)).date()
    title = f"Regulatory bulletin {state}-{index:03d}"
    body = f"Department bulletin for {state} covering fair-claims timing, documentation expectations, and adverse action disclosures."
    return _front_matter("regulatory_bulletin", title, "regulatory", state, 0.0, settled_date) + body


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_historical_corpus] Deterministic seed={SEED}")
    container = _blob_service(args.blob_account_name).get_container_client("historical")
    try:
        container.create_container()
    except ResourceExistsError:
        pass
    deleted = _clear_prefix(container, "claims/") + _clear_prefix(container, "endorsements/") + _clear_prefix(container, "bulletins/")
    print(f"[gen_historical_corpus] Cleared {deleted} existing historical blobs")
    uploaded = 0
    for index in range(1, 501):
        container.upload_blob(name=f"claims/hist-{index:03d}.md", data=_claim_markdown(index).encode("utf-8"), overwrite=True)
        uploaded += 1
    for index in range(1, 51):
        container.upload_blob(name=f"endorsements/endrs-{index:03d}.md", data=_endorsement_markdown(index).encode("utf-8"), overwrite=True)
        uploaded += 1
    for idx, state in enumerate(US_STATES[:10], start=1):
        for ordinal in range(1, 4):
            container.upload_blob(name=f"bulletins/reg-{state}-{ordinal:03d}.md", data=_bulletin_markdown(state, idx * 10 + ordinal).encode("utf-8"), overwrite=True)
            uploaded += 1
    summary = {"generator": "gen_historical_corpus", "claim_markdown": 500, "endorsements": 50, "bulletins": 30, "blobs": uploaded}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
