"""Audit view."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import Principal, require_role
from ..db import get_session
from ..schemas import AuditEventOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _rows(result) -> list[dict]:
    out = []
    for r in result.fetchall():
        d = dict(r._mapping)  # type: ignore[attr-defined]
        if isinstance(d.get("RationaleJson"), str):
            import json
            try:
                d["RationaleJson"] = json.loads(d["RationaleJson"])
            except json.JSONDecodeError:
                pass
        out.append(d)
    return out


@router.get("", response_model=list[AuditEventOut], response_model_by_alias=False)
def list_audit(
    claim_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsSupervisor", "SIU", "ClaimsAdjuster")),
) -> list[AuditEventOut]:
    if claim_id:
        result = s.execute(text("""
            SELECT * FROM dbo.AuditEvent WHERE ClaimId = :id ORDER BY CreatedUtc DESC
            OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY
        """), {"id": str(claim_id), "off": offset, "lim": limit})
    else:
        result = s.execute(text("""
            SELECT * FROM dbo.AuditEvent ORDER BY CreatedUtc DESC
            OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY
        """), {"off": offset, "lim": limit})
    return [AuditEventOut.model_validate(r) for r in _rows(result)]
