"""Benchmark operational log query plans before and after proposed indexes in memory."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path


CURRENT_INDEXES = (
    "CREATE INDEX idx_logs_facility_timestamp ON system_logs(facility_id, timestamp)",
    "CREATE INDEX idx_logs_server_timestamp ON system_logs(server_id, timestamp)",
    "CREATE INDEX idx_logs_event_timestamp ON system_logs(event_code, timestamp)",
)
PROPOSED_INDEXES = (
    "CREATE INDEX idx_logs_timestamp ON system_logs(timestamp)",
    "CREATE INDEX idx_logs_component_timestamp ON system_logs(component, timestamp)",
    "CREATE INDEX idx_logs_level_timestamp ON system_logs(log_level, timestamp)",
)
QUERIES = {
    "global_time_window": (
        "SELECT * FROM system_logs WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("2025-01-01", "2025-12-31T23:59"),
    ),
    "facility_timeline": (
        "SELECT * FROM system_logs WHERE facility_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("DC-FRA-01", "2025-01-01", "2025-12-31T23:59"),
    ),
    "server_timeline": (
        "SELECT * FROM system_logs WHERE server_id=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("SRV-00052", "2015-01-01", "2025-12-31T23:59"),
    ),
    "event_history": (
        "SELECT * FROM system_logs WHERE event_code=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("TEMP_HIGH", "2015-01-01", "2025-12-31T23:59"),
    ),
    "component_history": (
        "SELECT * FROM system_logs WHERE component=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("cooling", "2015-01-01", "2025-12-31T23:59"),
    ),
    "severity_history": (
        "SELECT * FROM system_logs WHERE log_level=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp LIMIT 200",
        ("CRITICAL", "2015-01-01", "2025-12-31T23:59"),
    ),
}


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentage
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def memory_copy(database: Path) -> sqlite3.Connection:
    source = sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)
    target = sqlite3.connect(":memory:")
    target.execute(
        """CREATE TABLE system_logs (
            log_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, facility_id TEXT NOT NULL,
            server_id TEXT NOT NULL, rack_id TEXT NOT NULL, source TEXT NOT NULL,
            component TEXT NOT NULL, log_level TEXT NOT NULL, event_code TEXT NOT NULL,
            message TEXT NOT NULL
        )"""
    )
    rows = source.execute("SELECT * FROM system_logs").fetchall()
    target.executemany("INSERT INTO system_logs VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    source.close()
    for statement in CURRENT_INDEXES:
        target.execute(statement)
    target.execute("ANALYZE")
    return target


def measure(connection: sqlite3.Connection, repetitions: int) -> dict[str, object]:
    output = {}
    for name, (sql, parameters) in QUERIES.items():
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql, parameters)]
        connection.execute(sql, parameters).fetchall()
        samples = []
        for _ in range(repetitions):
            started = time.perf_counter()
            rows = connection.execute(sql, parameters).fetchall()
            samples.append((time.perf_counter() - started) * 1000)
        output[name] = {
            "plan": plan,
            "row_count": len(rows),
            "p50_ms": round(statistics.median(samples), 4),
            "p95_ms": round(percentile(samples, 0.95), 4),
        }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/log_search_phase28.json"))
    args = parser.parse_args()
    connection = memory_copy(args.database)
    try:
        before = measure(connection, args.repetitions)
        for statement in PROPOSED_INDEXES:
            connection.execute(statement)
        connection.execute("ANALYZE")
        after = measure(connection, args.repetitions)
    finally:
        connection.close()
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": args.database.resolve().as_posix(),
        "method": "In-memory copy of system_logs; source database remains read-only and unchanged.",
        "row_count": 5790,
        "repetitions": args.repetitions,
        "current_indexes": list(CURRENT_INDEXES),
        "proposed_indexes": list(PROPOSED_INDEXES),
        "before": before,
        "after": after,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
