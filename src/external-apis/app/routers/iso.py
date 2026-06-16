"""ISO claim search mock endpoint."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/iso", tags=["ISO Claim Search"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "iso_claims.json"


class IsoClaimMatch(BaseModel):
    """Historical ISO claim match."""

    match_id: str
    claim_date: str
    loss_type: str
    amount: float
    claimant_name: str


class IsoClaimRecord(IsoClaimMatch):
    """Internal claim record with lookup attributes."""

    identifier: str
    vin: str


class IsoSearchResponse(BaseModel):
    """ISO search response payload."""

    matches: list[IsoClaimMatch] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _load_records() -> list[IsoClaimRecord]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_records = json.load(handle)
    return [IsoClaimRecord.model_validate(record) for record in raw_records]


@router.get("/search", response_model=IsoSearchResponse)
def search_iso_claims(
    identifier: Annotated[str | None, Query(min_length=8)] = None,
    vin: Annotated[str | None, Query(min_length=11, max_length=17)] = None,
) -> IsoSearchResponse:
    """Search synthetic ISO historical claims."""

    if identifier is None and vin is None:
        raise HTTPException(status_code=400, detail="Provide either identifier or vin.")

    matches = [
        IsoClaimMatch.model_validate(record.model_dump())
        for record in _load_records()
        if (identifier is None or record.identifier == identifier) and (vin is None or record.vin == vin)
    ]
    return IsoSearchResponse(matches=matches)
