"""Generate JSON corpora for the six mock external APIs."""
from __future__ import annotations

import argparse
import json
import random
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / ".seed_state" / "gen_sql_output.json"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent.parent / "src" / "external-apis" / "data"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reseed", action="store_true")
    return parser.parse_args(argv)


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Run gen_sql.py first; manifest not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_external_apis] Deterministic seed={SEED}")
    manifest = _load_manifest(args.manifest_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    demo_claims = {claim["claim_number"]: claim for claim in manifest["claims"][:10]}
    iso_claims = []
    ring_claims = [demo_claims[number] for number in ("CLM-200003", "CLM-200008", "CLM-200009", "CLM-200010")]
    for index in range(250):
        claim = manifest["claims"][index]
        iso_claims.append(
            {
                "match_id": f"ISO-{index + 1:04d}",
                "claim_number": claim["claim_number"],
                "identifier": claim["phone"] or claim["claim_number"],
                "state": claim["state"],
                "match_score": round(float(RNG.uniform(0.31, 0.97)), 3),
                "ring_id": claim.get("ring_id"),
            }
        )
    for ring_claim in ring_claims:
        iso_claims.append(
            {
                "match_id": f"ISO-DEMO-{ring_claim['claim_number']}",
                "claim_number": ring_claim["claim_number"],
                "identifier": ring_claim["phone"],
                "state": ring_claim["state"],
                "match_score": 0.98,
                "ring_id": ring_claim.get("ring_id"),
            }
        )
    iso_claims = iso_claims[:250]

    zip_codes = [claim["zip_code"] for claim in manifest["claims"][:10]]
    weather = []
    for zip_code in zip_codes:
        for day_offset in range(90):
            observed = datetime.now(UTC).date() - timedelta(days=day_offset)
            weather.append(
                {
                    "zip": zip_code,
                    "date": observed.isoformat(),
                    "condition": random.choice(["clear", "rain", "hail", "wind", "snow"]),
                    "severity": round(float(RNG.uniform(0.0, 9.9)), 2),
                }
            )

    police_reports = []
    for index in range(150):
        claim = manifest["claims"][index]
        police_reports.append(
            {
                "report_number": f"PR-{index + 1:05d}",
                "claim_number": claim["claim_number"],
                "officer": fake.name(),
                "narrative": fake.paragraph(nb_sentences=3),
                "state": claim["state"],
            }
        )

    avm_valuations = []
    for policy in manifest["policies"][:5000]:
        avm_valuations.append(
            {
                "policy_number": policy["policy_number"],
                "state": policy["state"],
                "vehicle_value": round(float(RNG.uniform(4200, 38800)), 2),
                "property_value": round(float(RNG.uniform(145000, 910000)), 2),
            }
        )

    cpt_codes = [f"{90000 + index}" for index in range(50)]
    medbill_prices = [
        {"cpt_code": code, "fair_price": round(float(RNG.uniform(85, 2450)), 2), "description": fake.sentence(nb_words=5)}
        for code in cpt_codes
    ]

    payment_ledger: list[dict[str, Any]] = []

    (args.output_dir / "iso_claims.json").write_text(json.dumps(iso_claims, indent=2), encoding="utf-8")
    (args.output_dir / "weather.json").write_text(json.dumps(weather, indent=2), encoding="utf-8")
    (args.output_dir / "police_reports.json").write_text(json.dumps(police_reports, indent=2), encoding="utf-8")
    (args.output_dir / "avm_valuations.json").write_text(json.dumps(avm_valuations, indent=2), encoding="utf-8")
    (args.output_dir / "medbill_prices.json").write_text(json.dumps(medbill_prices, indent=2), encoding="utf-8")
    (args.output_dir / "payment_ledger.json").write_text(json.dumps(payment_ledger, indent=2), encoding="utf-8")
    summary = {"generator": "gen_external_apis", "iso_claims": len(iso_claims), "weather": len(weather), "police_reports": len(police_reports), "avm_valuations": len(avm_valuations), "medbill_prices": len(medbill_prices), "payment_ledger": len(payment_ledger)}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
