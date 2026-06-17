"""Events router — exposes pipeline lifecycle events for the supervisor dashboard.

Events are persisted to dbo.PipelineEvent so they survive container restarts.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_session

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])


def record_event(event: dict[str, Any]) -> None:
    """Persist a pipeline lifecycle event to SQL."""
    s = SessionLocal()
    try:
        s.execute(text("""
            INSERT INTO dbo.PipelineEvent (EventId, EventType, ClaimId, ClaimNumber, Agent, CorrelationId, OccurredUtc, DetailJson)
            VALUES (:eid, :etype, :cid, :cnum, :agent, :corr, SYSUTCDATETIME(), :detail)
        """), {
            "eid": event.get("event_id", ""),
            "etype": event.get("event_type", ""),
            "cid": event.get("claim_id"),
            "cnum": event.get("claim_number"),
            "agent": event.get("agent"),
            "corr": event.get("correlation_id"),
            "detail": json.dumps(event.get("detail")) if event.get("detail") else None,
        })
        s.commit()
    except Exception:  # noqa: BLE001
        log.exception("Failed to persist pipeline event %s", event.get("event_id"))
        s.rollback()
    finally:
        s.close()


def _row_to_dict(row) -> dict[str, Any]:
    d = dict(row._mapping)  # type: ignore[attr-defined]
    detail = d.pop("DetailJson", None)
    return {
        "event_id": d.get("EventId"),
        "event_type": d.get("EventType"),
        "claim_id": d.get("ClaimId"),
        "claim_number": d.get("ClaimNumber"),
        "agent": d.get("Agent"),
        "correlation_id": d.get("CorrelationId"),
        "occurred_utc": d.get("OccurredUtc").isoformat() if d.get("OccurredUtc") else None,
        "detail": json.loads(detail) if detail else {},
    }


@router.get("/recent")
def get_recent_events(
    limit: int = 50,
    s: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    """Return the most recent pipeline lifecycle events from SQL."""
    result = s.execute(text("""
        SELECT TOP(:lim) * FROM dbo.PipelineEvent ORDER BY OccurredUtc DESC
    """), {"lim": limit})
    return [_row_to_dict(r) for r in result.fetchall()]
