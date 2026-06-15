"""Automated valuation model mock endpoints."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/avm", tags=["AVM"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "avm_valuations.json"


class AvmResponse(BaseModel):
    """Valuation response payload."""

    type: Literal["vehicle", "property"]
    identifier: str
    fair_market_value: float
    confidence: float = Field(ge=0.0, le=1.0)
    comparables_count: int = Field(ge=1)
    as_of_date: str


class AvmIndex(BaseModel):
    """Internal AVM data model."""

    vehicle: dict[str, AvmResponse]
    property: dict[str, AvmResponse]


@lru_cache(maxsize=1)
def _load_avm_index() -> AvmIndex:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_index = json.load(handle)
    return AvmIndex.model_validate(raw_index)


@router.get("/vehicle", response_model=AvmResponse)
def get_vehicle_valuation(
    vin: Annotated[str, Query(min_length=11, max_length=17)],
) -> AvmResponse:
    """Return a synthetic vehicle valuation by VIN."""

    valuation = _load_avm_index().vehicle.get(vin)
    if valuation is None:
        raise HTTPException(status_code=404, detail="Vehicle valuation not found.")
    return valuation


@router.get("/property", response_model=AvmResponse)
def get_property_valuation(
    address: Annotated[str, Query(min_length=5)],
) -> AvmResponse:
    """Return a synthetic property valuation by address."""

    valuation = _load_avm_index().property.get(address)
    if valuation is None:
        raise HTTPException(status_code=404, detail="Property valuation not found.")
    return valuation
