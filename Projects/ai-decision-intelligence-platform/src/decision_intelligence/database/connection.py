"""Secure SQL Server connection construction and lifecycle helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pyodbc

from decision_intelligence.settings import DatabaseSettings

LOGGER = logging.getLogger(__name__)


def _escape_odbc(value: str) -> str:
    """Brace and escape an ODBC value so separators cannot alter attributes."""
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(settings: DatabaseSettings, database: str | None = None) -> str:
    """Build a Windows-authenticated ODBC connection string without credentials."""
    target_database = database or settings.database
    parts = [
        f"DRIVER={_escape_odbc(settings.driver)}",
        f"SERVER={_escape_odbc(settings.server)}",
        f"DATABASE={_escape_odbc(target_database)}",
    ]
    if settings.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        if not settings.username or not settings.password:
            raise ValueError("SQL authentication requires username and password")
        parts.extend((
            "Trusted_Connection=no",
            f"UID={_escape_odbc(settings.username)}",
            f"PWD={_escape_odbc(settings.password)}",
        ))
    parts.extend((
        "Encrypt=yes",
        f"TrustServerCertificate={'yes' if settings.trust_server_certificate else 'no'}",
        "UseFMTONLY=yes",
        "APP=AI Decision Intelligence Platform",
    ))
    return ";".join(parts)


@contextmanager
def connect(
    settings: DatabaseSettings,
    database: str | None = None,
    *,
    autocommit: bool = False,
) -> Iterator[pyodbc.Connection]:
    """Open and reliably close a configured SQL Server connection."""
    connection: pyodbc.Connection | None = None
    target = database or settings.database
    try:
        connection = pyodbc.connect(
            build_connection_string(settings, target),
            timeout=settings.connection_timeout_seconds,
            autocommit=autocommit,
        )
        connection.timeout = settings.command_timeout_seconds
        yield connection
    except pyodbc.Error:
        LOGGER.exception("SQL Server operation failed for database %s", target)
        raise
    finally:
        if connection is not None:
            connection.close()


def fetch_scalar(connection: pyodbc.Connection, query: str, *parameters: Any) -> Any:
    """Execute a parameterized scalar query and reject an empty result."""
    row = connection.execute(query, parameters).fetchone()
    if row is None:
        raise RuntimeError("Scalar query returned no rows")
    return row[0]
