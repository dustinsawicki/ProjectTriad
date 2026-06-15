"""Payment disbursement mock endpoints."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/payment", tags=["Payments"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "payment_ledger.json"


class PaymentDisbursementRequest(BaseModel):
    """Payment disbursement request payload."""

    claim_id: str = Field(min_length=3)
    amount: float = Field(gt=0)
    payee: str = Field(min_length=2)
    method: Literal["ach", "check"]


class PaymentDisbursementResponse(BaseModel):
    """Payment disbursement response payload."""

    transaction_id: str
    status: Literal["completed"]
    disbursed_at: str
    claim_id: str
    amount: float


class PaymentLedgerResponse(BaseModel):
    """Payment ledger payload."""

    disbursements: list[PaymentDisbursementResponse]


def _load_seed_ledger() -> list[PaymentDisbursementResponse]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_entries = json.load(handle)
    return [PaymentDisbursementResponse.model_validate(entry) for entry in raw_entries]


_ledger: list[PaymentDisbursementResponse] = _load_seed_ledger()


@router.post("/disburse", response_model=PaymentDisbursementResponse)
def disburse_payment(payload: PaymentDisbursementRequest) -> PaymentDisbursementResponse:
    """Create a mock payment disbursement entry in the in-memory ledger."""

    disbursement = PaymentDisbursementResponse(
        transaction_id=f"txn-{uuid4().hex[:12]}",
        status="completed",
        disbursed_at=datetime.now(timezone.utc).isoformat(),
        claim_id=payload.claim_id,
        amount=round(payload.amount, 2),
    )
    _ledger.append(disbursement)
    return disbursement


@router.get("/ledger", response_model=PaymentLedgerResponse)
def get_payment_ledger() -> PaymentLedgerResponse:
    """Return the in-memory payment ledger."""

    return PaymentLedgerResponse(disbursements=list(_ledger))
