"""SQLAlchemy engine + session factory using Managed Identity tokens."""
from __future__ import annotations

import struct
from contextlib import contextmanager
from typing import Iterator

from azure.identity import DefaultAzureCredential
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_RESOURCE = "https://database.windows.net/.default"

_settings = get_settings()
_credential = DefaultAzureCredential()


def _make_connection_string() -> str:
    return (
        "mssql+pyodbc:///?odbc_connect="
        + (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={_settings.sql_server_fqdn},1433;"
            f"DATABASE={_settings.sql_database_name};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60;"
        ).replace(" ", "+")
    )


def _build_token_struct() -> bytes:
    token = _credential.get_token(_TOKEN_RESOURCE).token
    exp = b""
    for b in bytes(token, "utf-8"):
        exp += bytes([b]) + b"\0"
    return struct.pack("=i", len(exp)) + exp


def _provide_token(dialect, conn_rec, cargs, cparams):  # noqa: ARG001
    cparams["attrs_before"] = {_SQL_COPT_SS_ACCESS_TOKEN: _build_token_struct()}


def _make_engine() -> Engine:
    eng = create_engine(_make_connection_string(), pool_pre_ping=True, pool_size=5, max_overflow=5)
    event.listen(eng, "do_connect", _provide_token)
    return eng


_engine: Engine = _make_engine()
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
