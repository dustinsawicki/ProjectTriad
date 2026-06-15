"""Generate deterministic synthetic data for the mock external APIs service."""
from __future__ import annotations

import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from faker import Faker

random.seed(42)
Faker.seed(42)
fake = Faker("en_US")
fake.seed_instance(42)

DATA_DIR = Path(__file__).resolve().parent
ANCHOR_DATE = date(2026, 6, 15)
CLAIMS_START_DATE = date(2021, 1, 1)
REPORTS_START_DATE = date(2024, 1, 1)
VALUATION_START_DATE = ANCHOR_DATE - timedelta(days=30)
VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
LOSS_TYPES = [
    "auto_collision",
    "auto_theft",
    "hail_damage",
    "property_water",
    "property_fire",
    "bodily_injury",
]
WEATHER_PROFILES = {
    "clear": {"precipitation": (0.0, 0.0), "visibility": (8.5, 10.0), "temp": (61, 103)},
    "rain": {"precipitation": (0.05, 1.2), "visibility": (3.0, 7.0), "temp": (48, 84)},
    "storm": {"precipitation": (0.8, 2.8), "visibility": (1.0, 4.0), "temp": (52, 91)},
    "snow": {"precipitation": (0.1, 0.7), "visibility": (1.0, 5.0), "temp": (18, 35)},
    "fog": {"precipitation": (0.0, 0.1), "visibility": (0.2, 2.5), "temp": (35, 64)},
}
CPT_CODES = {
    "12001": "Simple repair of superficial wound",
    "12002": "Simple repair, scalp, neck, axillae, external genitalia, trunk and/or extremities",
    "20550": "Injection(s), single tendon sheath, or ligament",
    "20610": "Arthrocentesis, aspiration and/or injection; major joint",
    "21310": "Closed treatment of nasal bone fracture without manipulation",
    "22551": "Cervical discectomy and fusion",
    "23500": "Closed treatment of clavicular fracture",
    "23600": "Closed treatment of proximal humeral fracture",
    "24500": "Closed treatment of humeral shaft fracture",
    "24650": "Closed treatment of radial head fracture",
    "25500": "Closed treatment of radial shaft fracture",
    "25600": "Closed treatment of distal radial fracture",
    "26720": "Closed treatment of phalangeal shaft fracture",
    "27130": "Total hip arthroplasty",
    "27236": "Open treatment of femoral fracture, proximal end",
    "27506": "Open treatment of femoral shaft fracture",
    "27786": "Closed treatment of distal fibular fracture",
    "28470": "Closed treatment of metatarsal fracture",
    "29075": "Application of short arm cast",
    "29515": "Application of short leg splint",
    "29881": "Knee arthroscopy with meniscectomy",
    "36415": "Collection of venous blood by venipuncture",
    "36475": "Endovenous ablation therapy, first vein",
    "51798": "Measurement of post-void residual urine",
    "70450": "CT head/brain without contrast",
    "71045": "Radiologic examination, chest; single view",
    "72040": "Radiologic exam, spine, cervical; two or three views",
    "72125": "CT cervical spine without contrast",
    "72148": "MRI lumbar spine without contrast",
    "73030": "Radiologic exam, shoulder; complete",
    "73110": "Radiologic exam, wrist; complete",
    "73564": "Radiologic exam, knee; complete, four or more views",
    "73610": "Radiologic exam, ankle; complete",
    "73721": "MRI lower extremity joint without contrast",
    "74177": "CT abdomen and pelvis with contrast",
    "76700": "Ultrasound, abdominal, complete",
    "76830": "Ultrasound, transvaginal",
    "80048": "Basic metabolic panel",
    "80053": "Comprehensive metabolic panel",
    "81001": "Urinalysis, automated with microscopy",
    "85025": "Complete blood count with differential",
    "85730": "Thromboplastin time, partial",
    "87086": "Urine culture",
    "90791": "Psychiatric diagnostic evaluation",
    "90834": "Psychotherapy, 45 minutes",
    "93000": "Electrocardiogram with interpretation",
    "93224": "External electrocardiographic recording, 24 hours",
    "97110": "Therapeutic exercises",
    "97140": "Manual therapy techniques",
    "97530": "Therapeutic activities",
}


def write_json(filename: str, payload: Any) -> None:
    with (DATA_DIR / filename).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def generate_vin() -> str:
    return "".join(random.choice(VIN_CHARS) for _ in range(17))


def generate_iso_claims() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index in range(250):
        claimant_name = fake.name()
        identifier_source = f"{claimant_name}|{fake.ssn()}|{index}"
        records.append(
            {
                "identifier": hashlib.sha256(identifier_source.encode("utf-8")).hexdigest(),
                "vin": generate_vin(),
                "match_id": f"ISO-{index + 1:06d}",
                "claim_date": fake.date_between(start_date=CLAIMS_START_DATE, end_date=ANCHOR_DATE).isoformat(),
                "loss_type": random.choice(LOSS_TYPES),
                "amount": round(random.uniform(750.0, 42500.0), 2),
                "claimant_name": claimant_name,
            }
        )
    return records


def generate_weather() -> dict[str, dict[str, Any]]:
    weather_index: dict[str, dict[str, Any]] = {}
    zip_codes = [f"750{number:02d}" for number in range(1, 11)]
    weighted_conditions = (
        ["clear"] * 50
        + ["rain"] * 20
        + ["storm"] * 9
        + ["fog"] * 8
        + ["snow"] * 3
    )
    for day_offset in range(90):
        weather_date = (ANCHOR_DATE - timedelta(days=day_offset)).isoformat()
        for zip_code in zip_codes:
            condition = random.choice(weighted_conditions)
            profile = WEATHER_PROFILES[condition]
            weather_index[f"{zip_code}|{weather_date}"] = {
                "zip": zip_code,
                "date": weather_date,
                "condition": condition,
                "precipitation_in": round(random.uniform(*profile["precipitation"]), 2),
                "visibility_mi": round(random.uniform(*profile["visibility"]), 1),
                "temp_f": random.randint(*profile["temp"]),
            }
    return weather_index


def generate_police_reports() -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    citation_pool = [
        "speeding",
        "failure_to_yield",
        "following_too_closely",
        "reckless_driving",
        "improper_lane_change",
        "no_citation_issued",
    ]
    for index in range(150):
        report_no = f"PR-{index + 1:06d}"
        parties = [fake.name() for _ in range(random.randint(2, 4))]
        citations = sorted(set(random.sample(citation_pool, k=random.randint(1, 2))))
        reports[report_no] = {
            "report_no": report_no,
            "date": fake.date_between(start_date=REPORTS_START_DATE, end_date=ANCHOR_DATE).isoformat(),
            "officer": fake.name(),
            "narrative": fake.paragraph(nb_sentences=4),
            "parties": parties,
            "citations": citations,
        }
    return reports


def generate_avm_valuations() -> dict[str, dict[str, dict[str, Any]]]:
    vehicle_valuations: dict[str, dict[str, Any]] = {}
    property_valuations: dict[str, dict[str, Any]] = {}

    while len(vehicle_valuations) < 3000:
        vin = generate_vin()
        vehicle_valuations.setdefault(
            vin,
            {
                "type": "vehicle",
                "identifier": vin,
                "fair_market_value": round(random.uniform(6500.0, 78500.0), 2),
                "confidence": round(random.uniform(0.73, 0.98), 2),
                "comparables_count": random.randint(3, 12),
                "as_of_date": fake.date_between(start_date=VALUATION_START_DATE, end_date=ANCHOR_DATE).isoformat(),
            },
        )

    while len(property_valuations) < 2000:
        address = f"{fake.street_address()}, {fake.city()}, TX {fake.postcode()}"
        property_valuations.setdefault(
            address,
            {
                "type": "property",
                "identifier": address,
                "fair_market_value": round(random.uniform(145000.0, 1250000.0), 2),
                "confidence": round(random.uniform(0.7, 0.97), 2),
                "comparables_count": random.randint(4, 18),
                "as_of_date": fake.date_between(start_date=VALUATION_START_DATE, end_date=ANCHOR_DATE).isoformat(),
            },
        )

    return {"vehicle": vehicle_valuations, "property": property_valuations}


def generate_medbill_prices() -> dict[str, dict[str, Any]]:
    prices: dict[str, dict[str, Any]] = {}
    for code, description in CPT_CODES.items():
        prices[code] = {
            "description": description,
            "fair_price": round(random.uniform(45.0, 2400.0), 2),
        }
    return prices


def main() -> None:
    write_json("iso_claims.json", generate_iso_claims())
    write_json("weather.json", generate_weather())
    write_json("police_reports.json", generate_police_reports())
    write_json("avm_valuations.json", generate_avm_valuations())
    write_json("medbill_prices.json", generate_medbill_prices())
    write_json("payment_ledger.json", [])


if __name__ == "__main__":
    main()
