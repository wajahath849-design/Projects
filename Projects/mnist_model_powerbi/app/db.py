from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

import pyodbc

from . import config


def connection_string(database: str | None = None) -> str:
    db = database or config.DB_NAME
    return (
        f"DRIVER={{{config.DB_DRIVER}}};"
        f"SERVER={config.DB_SERVER};"
        f"DATABASE={db};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=8;"
    )


def connect(retries: int = 6, database: str | None = None, autocommit: bool = False) -> pyodbc.Connection:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            return pyodbc.connect(connection_string(database), autocommit=autocommit)
        except Exception as exc:  # pragma: no cover - depends on local SQL Server
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(min(0.5 * (attempt + 1), 3.0))
    assert last_error is not None
    raise last_error


def write_event(severity: str, component: str, event_code: str, message: str,
                batch_id: str | None = None, model_id: int | None = None) -> None:
    """Best-effort operational logging; event logging never breaks inference."""
    try:
        with connect(retries=2) as conn:
            conn.cursor().execute(
                """INSERT dbo.SystemEvent(Severity,Component,EventCode,Message,BatchID,ModelID)
                   VALUES(?,?,?,?,?,?)""",
                severity, component, event_code, str(message)[:4000], batch_id, model_id,
            )
            conn.commit()
    except Exception:
        return
