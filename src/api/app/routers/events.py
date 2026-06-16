"""Events router — exposes recent claim events for the dashboard."""

from fastapi import APIRouter
from typing import Any
from collections import deque

router = APIRouter(prefix="/api/events", tags=["events"])

# In-memory ring buffer of recent events (persisted across requests within the process)
_recent_events: deque[dict[str, Any]] = deque(maxlen=100)


def record_event(event: dict[str, Any]) -> None:
    """Called internally to record an event for the dashboard."""
    _recent_events.appendleft(event)


@router.get("/recent")
async def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent claim lifecycle events."""
    return list(_recent_events)[:limit]
