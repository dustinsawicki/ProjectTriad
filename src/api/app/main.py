"""FastAPI entrypoint."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import audit, claims, health, queue, events, siu, supervisor

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("claims-api")

settings = get_settings()

app = FastAPI(
    title="Agentic Claims Processing API",
    version="2.0.0",
    description="FSI PoC v2 — Event-driven multi-agent claims pipeline with RAG, vision, and link-graph fraud detection.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # PoC; locked by ACA ingress in prod
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(health.router)
app.include_router(queue.router)
app.include_router(claims.router)
app.include_router(audit.router)
app.include_router(events.router)
app.include_router(siu.router)
app.include_router(supervisor.router)


# Optional: Application Insights via OpenTelemetry
if settings.applicationinsights_connection_string:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(connection_string=settings.applicationinsights_connection_string)
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        log.info("App Insights configured")
    except Exception as e:  # noqa: BLE001
        log.warning("App Insights not configured: %s", e)


@app.on_event("startup")
def _startup() -> None:
    log.info("Claims API v2 starting; SQL=%s/%s", settings.sql_server_fqdn, settings.sql_database_name)
    log.info("Cosmos=%s, Blob=%s, Search=%s", settings.cosmos_endpoint, settings.blob_account_name, settings.search_endpoint)
