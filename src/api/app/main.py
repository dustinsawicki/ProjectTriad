"""FastAPI entrypoint."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import audit, claims, health, queue

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
log = logging.getLogger("claims-api")

settings = get_settings()

app = FastAPI(
    title="Agentic Claims Processing API",
    version="1.0.0",
    description="FSI PoC — Four-agent claims pipeline over Azure SQL.",
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
    log.info("Claims API starting; SQL=%s/%s", settings.sql_server_fqdn, settings.sql_database_name)
    # Register agents lazily — first /api/claims request creates them on demand
