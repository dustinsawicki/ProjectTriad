"""Events router — exposes recent claim events for the supervisor dashboard."""

import random
import uuid
from datetime import datetime, timedelta, timezone
from collections import deque
from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/events", tags=["events"])

# In-memory ring buffer of recent events (persisted across requests within the process)
_recent_events: deque[dict[str, Any]] = deque(maxlen=200)


def record_event(event: dict[str, Any]) -> None:
    """Called internally to record an event for the dashboard."""
    _recent_events.appendleft(event)


def _seed_demo_events() -> int:
    """Generate synthetic pipeline events for demo purposes."""
    if len(_recent_events) > 0:
        return 0

    event_types = [
        ("fnol_complete", "FnolDocumentAgent"),
        ("triage_complete", "TriageCoverageAgent"),
        ("assessment_complete", "AssessmentSettlementAgent"),
        ("guardrail_complete", "GuardrailsAgent"),
        ("pipeline_complete", None),
    ]
    routes = ["stp", "desk", "field", "siu"]
    outcomes = ["pass", "pass", "pass", "block"]
    now = datetime.now(timezone.utc)
    count = 0

    for i in range(25):
        claim_num = f"CLM-{900000 + i:06d}"
        claim_id = str(uuid.uuid4())
        corr = f"corr-{uuid.uuid4().hex[:12]}"
        base_time = now - timedelta(minutes=random.randint(5, 1440))
        route = random.choice(routes)
        fraud = round(random.uniform(0.05, 0.95), 2)

        for j, (etype, agent) in enumerate(event_types):
            if etype in ("assessment_complete", "guardrail_complete") and route in ("field", "siu"):
                continue

            detail: dict[str, Any] = {}
            if etype == "triage_complete":
                detail = {"route": route, "fraud_score": fraud}
            elif etype == "assessment_complete":
                detail = {"settlement_amount": random.randint(500, 50000)}
            elif etype == "guardrail_complete":
                detail = {"outcome": random.choice(outcomes)}
            elif etype == "pipeline_complete":
                detail = {"route": route}

            evt = {
                "event_id": f"evt-{uuid.uuid4().hex[:12]}",
                "event_type": etype,
                "claim_id": claim_id,
                "claim_number": claim_num,
                "agent": agent,
                "correlation_id": corr,
                "occurred_utc": (base_time + timedelta(seconds=j * random.randint(2, 15))).isoformat(),
                "detail": detail,
            }
            _recent_events.append(evt)
            count += 1

    # Sort by occurred_utc descending (most recent first)
    sorted_events = sorted(_recent_events, key=lambda e: e["occurred_utc"], reverse=True)
    _recent_events.clear()
    _recent_events.extend(sorted_events)
    return count


@router.get("/recent")
async def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent claim lifecycle events."""
    return list(_recent_events)[:limit]


@router.post("/seed", status_code=201)
async def seed_events() -> dict[str, Any]:
    """Seed demo events into the in-memory buffer."""
    _recent_events.clear()
    count = _seed_demo_events()
    return {"seeded": count}


# Auto-seed on module load so the supervisor dashboard has data immediately
_seed_demo_events()
