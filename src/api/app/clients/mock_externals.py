"""Client for mock external APIs (ISO, weather, police, AVM, medbill, payment)."""

import httpx
from typing import Any

from app.config import settings


_BASE_URL = settings.EXTERNAL_API_BASE_URL.rstrip("/")


async def call_iso_claim_search(identifier: str | None = None, vin: str | None = None) -> dict[str, Any]:
    """Search ISO ClaimSearch by hashed identifier or VIN."""
    params = {}
    if identifier:
        params["identifier"] = identifier
    if vin:
        params["vin"] = vin
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}/iso/search", params=params)
        resp.raise_for_status()
        return resp.json()


async def call_weather(zip_code: str, date: str) -> dict[str, Any]:
    """Get weather conditions for a ZIP and date."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}/weather", params={"zip": zip_code, "date": date})
        resp.raise_for_status()
        return resp.json()


async def call_police_report(report_no: str) -> dict[str, Any]:
    """Retrieve a police report by report number."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}/police-report/{report_no}")
        resp.raise_for_status()
        return resp.json()


async def call_avm_vehicle(vin: str) -> dict[str, Any]:
    """Get automated valuation for a vehicle."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}/avm/vehicle", params={"vin": vin})
        resp.raise_for_status()
        return resp.json()


async def call_avm_property(address: str) -> dict[str, Any]:
    """Get automated valuation for a property."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_BASE_URL}/avm/property", params={"address": address})
        resp.raise_for_status()
        return resp.json()


async def call_medbill_review(line_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Review medical bill line items for fair pricing."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{_BASE_URL}/medbill/review", json={"line_items": line_items})
        resp.raise_for_status()
        return resp.json()


async def disburse_payment(claim_id: str, amount: float, payee: str, method: str = "ach") -> dict[str, Any]:
    """Disburse payment for a settled claim."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{_BASE_URL}/payment/disburse",
            json={"claim_id": claim_id, "amount": amount, "payee": payee, "method": method},
        )
        resp.raise_for_status()
        return resp.json()
