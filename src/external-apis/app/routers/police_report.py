"""Police report lookup mock endpoint."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Path as ApiPath
from pydantic import BaseModel, Field

router = APIRouter(tags=["Police Reports"])
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "police_reports.json"


class PoliceReportResponse(BaseModel):
    """Police report stub payload."""

    report_no: str = Field(pattern=r"^PR-\d{6}$")
    date: str
    officer: str
    narrative: str
    parties: list[str]
    citations: list[str]


@lru_cache(maxsize=1)
def _load_reports() -> dict[str, PoliceReportResponse]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        raw_reports = json.load(handle)
    return {report_no: PoliceReportResponse.model_validate(report) for report_no, report in raw_reports.items()}


@router.get("/police-report/{report_no}", response_model=PoliceReportResponse)
def get_police_report(
    report_no: str = ApiPath(pattern=r"^PR-\d{6}$"),
) -> PoliceReportResponse:
    """Return a synthetic police report stub."""

    report = _load_reports().get(report_no)
    if report is None:
        raise HTTPException(status_code=404, detail="Police report not found.")
    return report
