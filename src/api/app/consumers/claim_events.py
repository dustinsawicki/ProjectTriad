"""Event Hub consumer that dispatches claim events to the appropriate agent."""

import asyncio
import json
import logging
from typing import Any

from azure.eventhub.aio import EventHubConsumerClient
from azure.identity.aio import DefaultAzureCredential

from app.config import settings

logger = logging.getLogger(__name__)

# Map event types to handler functions
EVENT_HANDLERS: dict[str, Any] = {}


def register_handler(event_type: str):
    """Decorator to register an event handler."""
    def decorator(func):
        EVENT_HANDLERS[event_type] = func
        return func
    return decorator


async def process_event(event):
    """Process a single event from the claim-events hub."""
    body = json.loads(event.body_as_str())
    event_type = body.get("event_type")
    claim_id = body.get("claim_id")
    correlation_id = body.get("correlation_id")

    logger.info(
        f"Processing event: type={event_type}, claim={claim_id}, corr={correlation_id}"
    )

    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            await handler(body)
        except Exception as e:
            logger.error(f"Handler failed for {event_type}: {e}", exc_info=True)
    else:
        logger.warning(f"No handler registered for event type: {event_type}")


async def on_event(partition_context, event):
    """Callback for each event received."""
    await process_event(event)
    await partition_context.update_checkpoint(event)


async def start_consumer():
    """Start the Event Hub consumer for claim-events. Runs until cancelled."""
    credential = DefaultAzureCredential()
    client = EventHubConsumerClient(
        fully_qualified_namespace=settings.EVENT_HUB_NAMESPACE_FQDN,
        eventhub_name="claim-events",
        consumer_group="api-consumer",
        credential=credential,
    )

    logger.info("Starting claim-events consumer...")
    async with client:
        await client.receive(
            on_event=on_event,
            starting_position="-1",  # Start from latest
        )
