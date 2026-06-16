"""Medical bill review mock endpoint."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/medbill", tags=["Medical Bill Review"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "medbill_prices.json"


class MedbillLineItem(BaseModel):
    """Medical bill line item."""

    cpt_code: str = Field(pattern=r"^\d{5}$")
    charges: float = Field(gt=0)
    units: int = Field(gt=0)


class MedbillReviewRequest(BaseModel):
    """Medical bill review request payload."""

    line_items: list[MedbillLineItem] = Field(min_length=1)


class MedbillReviewedItem(BaseModel):
    """Reviewed medical bill line item."""

    cpt_code: str
    original_charges: float
    fair_price: float
    reduction_pct: float


class MedbillReviewResponse(BaseModel):
    """Medical bill review response payload."""

    reviewed_items: list[MedbillReviewedItem]
    total_original: float
    total_repriced: float
    total_savings: float


class MedbillPriceEntry(BaseModel):
    """Fair-price table entry."""

    description: str
    fair_price: float = Field(gt=0)


@lru_cache(maxsize=1)
def _load_price_table() -> dict[str, MedbillPriceEntry]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_price_table = json.load(handle)
    return {code: MedbillPriceEntry.model_validate(entry) for code, entry in raw_price_table.items()}


@router.post("/review", response_model=MedbillReviewResponse)
def review_medical_bill(payload: MedbillReviewRequest) -> MedbillReviewResponse:
    """Reprice medical bill line items using the fair-price table."""

    price_table = _load_price_table()
    missing_codes = sorted({item.cpt_code for item in payload.line_items if item.cpt_code not in price_table})
    if missing_codes:
        raise HTTPException(status_code=404, detail=f"Unknown CPT code(s): {', '.join(missing_codes)}")

    reviewed_items: list[MedbillReviewedItem] = []
    total_original = 0.0
    total_repriced = 0.0

    for item in payload.line_items:
        original_charges = round(item.charges, 2)
        fair_price = round(price_table[item.cpt_code].fair_price * item.units, 2)
        reduction_pct = round(max(0.0, ((original_charges - fair_price) / original_charges) * 100), 2)
        reviewed_items.append(
            MedbillReviewedItem(
                cpt_code=item.cpt_code,
                original_charges=original_charges,
                fair_price=fair_price,
                reduction_pct=reduction_pct,
            )
        )
        total_original += original_charges
        total_repriced += fair_price

    total_original = round(total_original, 2)
    total_repriced = round(total_repriced, 2)
    return MedbillReviewResponse(
        reviewed_items=reviewed_items,
        total_original=total_original,
        total_repriced=total_repriced,
        total_savings=round(total_original - total_repriced, 2),
    )
