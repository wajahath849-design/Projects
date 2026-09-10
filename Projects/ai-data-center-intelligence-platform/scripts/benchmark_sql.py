"""Benchmark representative SQLite analytical queries and capture their plans."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def percentile(values: list[float], percentage: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentage
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def normalize(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 8)
    return value


def execute(connection: sqlite3.Connection, sql: str) -> tuple[list[str], list[list[Any]]]:
    cursor = connection.execute(sql)
    columns = [description[0] for description in cursor.description]
    rows = [[normalize(value) for value in row] for row in cursor.fetchall()]
    return columns, rows


def result_hash(columns: list[str], rows: list[list[Any]]) -> str:
    payload = json.dumps({"columns": columns, "rows": rows}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def benchmark_query(
    connection: sqlite3.Connection,
    definition: dict[str, str],
    variant: str,
    repetitions: int,
    warmups: int,
) -> dict[str, Any]:
    sql_key = "raw_sql" if variant == "before" else "optimized_sql"
    sql = definition[sql_key]
    if not sql.lstrip().lower().startswith(("select", "with")):
        raise ValueError(f"Benchmark query {definition['id']} is not read-only")
    plan = [row[3] for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}")]
    for _ in range(warmups):
        execute(connection, sql)
    samples: list[float] = []
    columns: list[str] = []
    rows: list[list[Any]] = []
    for _ in range(repetitions):
        started = time.perf_counter()
        columns, rows = execute(connection, sql)
        samples.append((time.perf_counter() - started) * 1000)
    return {
        "id": definition["id"],
        "category": definition["category"],
        "question": definition["question"],
        "sql": sql,
        "query_plan": plan,
        "row_count": len(rows),
        "result_sha256": result_hash(columns, rows),
        "samples_ms": [round(value, 3) for value in samples],
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
        "max_ms": round(max(samples), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--queries", type=Path, default=Path("evaluation/sql_performance_queries.json"))
    parser.add_argument("--variant", choices=("before", "after"), required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmups < 0:
        parser.error("repetitions must be positive and warmups cannot be negative")

    database = args.database.resolve()
    definitions = json.loads(args.queries.read_text(encoding="utf-8"))
    uri = f"file:{database.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        results = []
        for index, definition in enumerate(definitions, start=1):
            result = benchmark_query(
                connection, definition, args.variant, args.repetitions, args.warmups
            )
            results.append(result)
            print(
                f"[{index}/{len(definitions)}] {result['id']}: "
                f"P50 {result['p50_ms']:.3f} ms",
                flush=True,
            )
        all_samples = [sample for result in results for sample in result["samples_ms"]]
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "variant": args.variant,
            "database": database.as_posix(),
            "database_bytes": database.stat().st_size,
            "sqlite_version": sqlite3.sqlite_version,
            "repetitions": args.repetitions,
            "warmups": args.warmups,
            "summary": {
                "query_count": len(results),
                "sample_count": len(all_samples),
                "p50_ms": round(statistics.median(all_samples), 3),
                "p95_ms": round(percentile(all_samples, 0.95), 3),
                "max_ms": round(max(all_samples), 3),
            },
            "queries": results,
        }
    finally:
        connection.close()

    output = args.output or Path(f"evaluation/results/sql_performance_{args.variant}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
