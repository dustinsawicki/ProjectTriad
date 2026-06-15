"""Azure Event Hubs client for publishing and consuming claim events."""

import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from azure.eventhub import EventHubProducerClient, EventData
from azure.identity import DefaultAzureCredential

from app.config import settings


def _get_producer(hub_name: str) -> EventHubProducerClient:
    credential = DefaultAzureCredential()
    return EventHubProducerClient(
        fully_qualified_namespace=settings.EVENT_HUB_NAMESPACE_FQDN,
        eventhub_name=hub_name,
        credential=credential,
    )


def publish_claim_event(
    event_type: str,
    claim_id: str,
    claim_number: str,
    data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> str:
    """Publish an event to the claim-events hub. Returns the event_id."""
    event_id = str(uuid4())
    envelope = {
        "event_id": event_id,
        "event_type": event_type,
        "claim_id": claim_id,
        "claim_number": claim_number,
        "occurred_utc": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id or f"corr-{claim_number}",
        "data": data or {},
    }
    producer = _get_producer("claim-events")
    with producer:
        batch = producer.create_batch()
        batch.add(EventData(json.dumps(envelope)))
        producer.send_batch(batch)
    return event_id


def publish_telematics_events(events: list[dict[str, Any]]) -> int:
    """Publish telematics events to the telematics-stream hub. Returns count sent."""
    producer = _get_producer("telematics-stream")
    count = 0
    with producer:
        batch = producer.create_batch()
        for evt in events:
            try:
                batch.add(EventData(json.dumps(evt)))
                count += 1
            except ValueError:
                # Batch full, send and start new
                producer.send_batch(batch)
                batch = producer.create_batch()
                batch.add(EventData(json.dumps(evt)))
                count += 1
        if count > 0:
            producer.send_batch(batch)
    return count
