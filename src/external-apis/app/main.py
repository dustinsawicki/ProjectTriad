"""FastAPI entrypoint for the mock external APIs service."""
from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .routers import avm, iso, medbill, payment, police_report, weather


class HealthResponse(BaseModel):
    """Health probe response."""

    status: str


app = FastAPI(
    title="Claims PoC - Mock External APIs",
    version="1.0.0",
    openapi_tags=[
        {"name": "ISO Claim Search", "description": "Historical claims lookups by hashed identifier or VIN."},
        {"name": "Weather", "description": "Weather history lookups by ZIP code and date."},
        {"name": "Police Reports", "description": "Police report stub retrieval by report number."},
        {"name": "AVM", "description": "Automated vehicle and property valuation lookups."},
        {"name": "Medical Bill Review", "description": "Medical bill repricing against a fair-price table."},
        {"name": "Payments", "description": "Mock payment disbursement and in-memory ledger endpoints."},
    ],
)

app.include_router(iso.router)
app.include_router(weather.router)
app.include_router(police_report.router)
app.include_router(avm.router)
app.include_router(medbill.router)
app.include_router(payment.router)


@app.get("/healthz", response_model=HealthResponse, tags=["Health"])
def healthz() -> HealthResponse:
    """Liveness probe."""

    return HealthResponse(status="ok")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=False)
