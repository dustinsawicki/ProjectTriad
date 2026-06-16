"""Entra ID bearer token validation + app-role checks."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Iterable

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import jwt
from jose.exceptions import JWTError

from .config import get_settings

_settings = get_settings()
_ISSUERS = (
    f"https://login.microsoftonline.com/{_settings.azure_tenant_id}/v2.0",
    f"https://sts.windows.net/{_settings.azure_tenant_id}/",
)
_JWKS_URL = f"https://login.microsoftonline.com/{_settings.azure_tenant_id}/discovery/v2.0/keys"


class Principal(dict):
    @property
    def oid(self) -> str | None:
        return self.get("oid")

    @property
    def upn(self) -> str:
        return self.get("preferred_username") or self.get("upn") or self.get("email") or "unknown"

    @property
    def roles(self) -> list[str]:
        return list(self.get("roles") or [])


@lru_cache(maxsize=1)
def _jwks_cache() -> tuple[dict, float]:
    return ({}, 0.0)


def _fetch_jwks() -> dict:
    cache, fetched_at = _jwks_cache.__wrapped__()  # type: ignore[attr-defined]
    now = time.time()
    if cache and now - fetched_at < 3600:
        return cache
    resp = httpx.get(_JWKS_URL, timeout=10.0)
    resp.raise_for_status()
    keys = {k["kid"]: k for k in resp.json()["keys"]}
    _jwks_cache.cache_clear()
    _jwks_cache.__wrapped__ = lambda: (keys, now)  # type: ignore[attr-defined]
    return keys


def _validate(token: str) -> Principal:
    try:
        header = jwt.get_unverified_header(token)
        keys = _fetch_jwks()
        key = keys.get(header["kid"])
        if key is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=None,
            options={"verify_aud": False},
            issuer=_ISSUERS[0],
        )
        if claims.get("iss") not in _ISSUERS:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad issuer")
        return Principal(claims)
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e


def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        # PoC dev mode: bypass auth when POC_AUTH_BYPASS=1 or no tenant configured
        if _settings.azure_tenant_id in ("", "dev") or _settings.poc_auth_bypass:
            return Principal({"preferred_username": "dev@local", "roles": ["ClaimsAdjuster", "ClaimsSupervisor", "SIU"]})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return _validate(authorization.split(" ", 1)[1])


def require_role(*allowed: str):
    allowed_set = set(allowed)

    def _dep(p: Principal = Depends(get_principal)) -> Principal:
        if allowed_set.isdisjoint(p.roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires one of: {sorted(allowed_set)}")
        return p

    return _dep
