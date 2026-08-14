from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_read_only(path: Path | str) -> sqlite3.Connection:
    database = Path(path).resolve()
    if not database.exists():
        raise FileNotFoundError(f"Database not found: {database}")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def discover_schema(path: Path | str) -> dict[str, set[str]]:
    with connect_read_only(path) as connection:
        objects = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {
            row["name"]: {column["name"] for column in connection.execute(f'PRAGMA table_info("{row["name"]}")')}
            for row in objects
        }
