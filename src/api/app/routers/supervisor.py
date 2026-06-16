"""Supervisor router — replay telematics and dashboard support."""

from fastapi import APIRouter, BackgroundTasks
from typing import Any

from app.clients.cosmos import get_database
from app.clients.eventhub import publish_telematics_events

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])


async def _replay_last_24h():
    """Fetch last 24h of telematics from Cosmos and push to Event Hubs."""
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    db = get_database()
    container = db.get_container_client("telematics")

    query = "SELECT * FROM c WHERE c.ts >= @cutoff ORDER BY c.ts"
    params = [{"name": "@cutoff", "value": cutoff}]
    events = list(container.query_items(
        query=query, parameters=params, enable_cross_partition_query=True
    ))

    if events:
        publish_telematics_events(events)

    return len(events)


@router.post("/replay-telematics", status_code=202)
async def replay_telematics(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Trigger a replay of last 24h telematics events to Event Hubs."""
    background_tasks.add_task(_replay_last_24h)
    return {"status": "accepted", "message": "Telematics replay triggered"}
