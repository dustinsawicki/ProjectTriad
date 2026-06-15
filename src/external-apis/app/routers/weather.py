"""Weather lookup mock endpoint."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(tags=["Weather"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "weather.json"


class WeatherResponse(BaseModel):
    """Weather lookup response payload."""

    zip: str = Field(pattern=r"^\d{5}$")
    date: str
    condition: str
    precipitation_in: float
    visibility_mi: float
    temp_f: int


@lru_cache(maxsize=1)
def _load_weather_index() -> dict[str, WeatherResponse]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_index = json.load(handle)
    return {key: WeatherResponse.model_validate(value) for key, value in raw_index.items()}


@router.get("/weather", response_model=WeatherResponse)
def get_weather(
    zip_code: Annotated[str, Query(alias="zip", pattern=r"^\d{5}$")],
    date: Annotated[str, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")],
) -> WeatherResponse:
    """Return synthetic historical weather for a ZIP code and date."""

    weather_record = _load_weather_index().get(f"{zip_code}|{date}")
    if weather_record is None:
        raise HTTPException(status_code=404, detail="Weather record not found.")
    return weather_record
