"""Claim CRUD + pipeline trigger + approve/sendback."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import Principal, require_role
from ..db import get_session, session_scope
from ..repositories import claims as repo
from ..schemas import (
    ApproveClaimIn,
    ClaimBundleOut,
    CreateClaimIn,
    CreateClaimOut,
    SendBackIn,
)
from ..services.orchestrator import run_pipeline

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.post("", response_model=CreateClaimOut, status_code=201)
def create_claim(
    body: CreateClaimIn,
    background: BackgroundTasks,
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsAdjuster", "ClaimsSupervisor")),
) -> CreateClaimOut:
    policy = repo.get_policy_by_number(s, body.policy_number)
    if not policy:
        raise HTTPException(422, f"Policy {body.policy_number} not found")

    cid, claim_no = repo.create_claim(
        s,
        policy_id=policy["PolicyId"],
        loss_datetime=body.loss_datetime,
        loss_type=body.loss_type,
        reported_amount=body.reported_amount,
    )
    for d in body.documents:
        repo.insert_document(s, claim_id=cid, doc_type=d.doc_type, title=d.title, raw_text=d.raw_text)
    s.commit()

    # Kick off the agent pipeline in the background
    corr = f"corr-{claim_no}"

    def _run() -> None:
        try:
            run_pipeline(str(cid), body.policy_number)
        except Exception:  # noqa: BLE001
            # The orchestrator already logs; never let bg crashes leak
            pass

    background.add_task(_run)
    return CreateClaimOut(claim_id=cid, claim_number=claim_no, pipeline_correlation_id=corr)


@router.get("/{claim_id}", response_model=ClaimBundleOut)
def get_claim(
    claim_id: UUID,
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsAdjuster", "ClaimsSupervisor", "SIU")),
) -> ClaimBundleOut:
    bundle = repo.get_claim_bundle(s, claim_id)
    if not bundle:
        raise HTTPException(404, "Claim not found")
    return ClaimBundleOut.model_validate(bundle)


@router.post("/{claim_id}/approve")
def approve_claim(
    claim_id: UUID,
    body: ApproveClaimIn,
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsAdjuster", "ClaimsSupervisor")),
) -> dict[str, str]:
    bundle = repo.get_claim_bundle(s, claim_id)
    if not bundle:
        raise HTTPException(404, "Claim not found")
    repo.settle(s, claim_id, body.settlement_amount)
    repo.insert_audit_event(
        s, claim_id=claim_id, decision_id=None, rule_id=None,
        actor="human", actor_name=p.upn, action="claim.approve_and_pay",
        outcome="approve",
        rationale={"settlement_amount": body.settlement_amount, "notes": body.notes},
        correlation_id=f"corr-{bundle['claim']['ClaimNumber']}",
    )
    s.commit()
    return {"status": "settled"}


@router.post("/{claim_id}/send_back")
def send_back(
    claim_id: UUID,
    body: SendBackIn,
    s: Session = Depends(get_session),
    p: Principal = Depends(require_role("ClaimsAdjuster", "ClaimsSupervisor")),
) -> dict[str, str]:
    repo.update_decision_status(s, body.decision_id, "edited")
    repo.insert_audit_event(
        s, claim_id=claim_id, decision_id=body.decision_id, rule_id=None,
        actor="human", actor_name=p.upn, action="claim.send_back", outcome="edit",
        rationale={"notes": body.notes}, correlation_id=None,
    )
    s.commit()
    return {"status": "edited"}
