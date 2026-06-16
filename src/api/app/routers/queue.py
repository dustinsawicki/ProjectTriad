"""Claims queue endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import Principal, require_role
from ..db import get_session
from ..repositories import claims as repo
from ..schemas import ClaimSummaryOut

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.get("", response_model=list[ClaimSummaryOut], response_model_by_alias=False)
def list_queue(
    status: str | None = Query(default=None),
    route: str | None = Query(default=None),
    min_fraud_score: float | None = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsAdjuster", "ClaimsSupervisor", "SIU")),
) -> list[ClaimSummaryOut]:
    rows = repo.list_claims(s, status=status, route=route, min_fraud_score=min_fraud_score, limit=limit, offset=offset)
    out: list[ClaimSummaryOut] = []
    for r in rows:
        out.append(ClaimSummaryOut(
            **{k: r.get(k) for k in ("ClaimId", "ClaimNumber", "LossType", "Status",
                                     "ReportedAmount", "ReserveAmount", "SettledAmount",
                                     "AssignedAdjuster", "CreatedUtc")},
            top_fraud_score=r.get("top_fraud_score"),
            route=(r.get("TriageDecisionJson") or {}).get("route") if isinstance(r.get("TriageDecisionJson"), dict) else None,
        ))
    return out
