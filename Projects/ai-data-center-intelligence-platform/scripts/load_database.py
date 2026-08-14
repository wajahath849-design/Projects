"""Build the SQLite analytical database atomically from canonical processed CSVs."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


LOAD_ORDER = (
    "facilities",
    "servers",
    "server_metrics",
    "power_metrics",
    "network_metrics",
    "uptime_incidents",
)


def load_csv(connection: sqlite3.Connection, csv_path: Path, table: str) -> int:
    row_count = 0
    for chunk in pd.read_csv(csv_path, chunksize=100_000, low_memory=False):
        chunk.to_sql(table, connection, if_exists="append", index=False, method="multi", chunksize=500)
        row_count += len(chunk)
    return row_count


def validate_database(connection: sqlite3.Connection) -> dict[str, object]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in LOAD_ORDER
    }
    views = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name"
        )
    ]
    indexes = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        "integrity_check": integrity,
        "foreign_key_violations": len(foreign_keys),
        "row_counts": counts,
        "views": views,
        "indexes": indexes,
    }


def build_database(
    data_dir: Path, database_path: Path, schema_path: Path, views_path: Path
) -> dict[str, object]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = database_path.with_suffix(database_path.suffix + ".building")
    temporary_path.unlink(missing_ok=True)

    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        loaded = {}
        with connection:
            for table in LOAD_ORDER:
                loaded[table] = load_csv(connection, data_dir / f"{table}.csv", table)
        connection.executescript(views_path.read_text(encoding="utf-8"))
        validation = validate_database(connection)
        if validation["integrity_check"] != "ok" or validation["foreign_key_violations"]:
            raise RuntimeError(f"Database validation failed: {validation}")
        connection.execute("PRAGMA optimize")
        connection.commit()
    finally:
        connection.close()

    os.replace(temporary_path, database_path)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": data_dir.as_posix(),
        "database_path": database_path.as_posix(),
        "loaded_rows": loaded,
        "validation": validation,
        "database_bytes": database_path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical SQLite database.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--schema", type=Path, default=Path("database/schema.sql"))
    parser.add_argument("--views", type=Path, default=Path("database/views.sql"))
    parser.add_argument("--audit", type=Path, default=Path("docs/step5_database_audit.json"))
    args = parser.parse_args()
    audit = build_database(args.data_dir, args.database, args.schema, args.views)
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit["validation"], indent=2))


if __name__ == "__main__":
    main()

