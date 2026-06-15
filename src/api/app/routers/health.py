"""Health endpoints — no auth required."""
from fastapi import APIRouter
from sqlalchemy import text

from ..db import session_scope

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        with session_scope() as s:
            s.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:  # noqa: BLE001
        return {"status": "degraded", "reason": str(e)}
