"""Rebuild governed analytical aggregates without modifying canonical raw rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path


def validate(connection: sqlite3.Connection) -> dict[str, object]:
    row_count = connection.execute("SELECT COUNT(*) FROM agg_facility_yearly").fetchone()[0]
    expected = connection.execute(
        """SELECT COUNT(*)
        FROM facilities
        CROSS JOIN (
            SELECT DISTINCT CAST(substr(timestamp, 1, 4) AS INTEGER) AS year
            FROM power_metrics
        )"""
    ).fetchone()[0]
    duplicate_count = connection.execute(
        """SELECT COUNT(*) FROM (
            SELECT facility_id, year
            FROM agg_facility_yearly
            GROUP BY facility_id, year
            HAVING COUNT(*) > 1
        )"""
    ).fetchone()[0]
    missing_measurements = connection.execute(
        """SELECT COUNT(*)
        FROM agg_facility_yearly
        WHERE server_measurement_count = 0
           OR power_measurement_count = 0
           OR network_measurement_count = 0"""
    ).fetchone()[0]
    foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "row_count": row_count,
        "expected_row_count": expected,
        "duplicate_grains": duplicate_count,
        "rows_missing_core_measurements": missing_measurements,
        "foreign_key_violations": len(foreign_key_violations),
        "valid": row_count == expected
        and duplicate_count == 0
        and missing_measurements == 0
        and not foreign_key_violations,
    }


def build(database: Path, definition: Path) -> dict[str, object]:
    started = time.perf_counter()
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        sql = definition.read_text(encoding="utf-8")
        connection.executescript(f"BEGIN IMMEDIATE;\n{sql}\nCOMMIT;")
        connection.execute("ANALYZE agg_facility_yearly")
        connection.execute("PRAGMA optimize")
        connection.commit()
        validation = validate(connection)
        if not validation["valid"]:
            raise RuntimeError(f"Aggregate validation failed: {validation}")
        planner_stats = connection.execute(
            "SELECT idx, stat FROM sqlite_stat1 WHERE tbl = 'agg_facility_yearly' ORDER BY idx"
        ).fetchall()
    finally:
        connection.close()
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": database.resolve().as_posix(),
        "definition": definition.resolve().as_posix(),
        "build_ms": round((time.perf_counter() - started) * 1000, 3),
        "validation": validation,
        "planner_stats": [{"index": row[0], "stat": row[1]} for row in planner_stats],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--definition", type=Path, default=Path("database/aggregates.sql"))
    parser.add_argument(
        "--audit", type=Path, default=Path("evaluation/results/aggregate_build.json")
    )
    args = parser.parse_args()
    report = build(args.database, args.definition)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
