"""Validate Phase 2 database correctness, benchmark equivalence, and regressions."""

from __future__ import annotations

import argparse
import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


RAW_COUNTS = {
    "facilities": 6,
    "servers": 430,
    "server_metrics": 1_727_740,
    "power_metrics": 24_108,
    "network_metrics": 24_108,
    "uptime_incidents": 1_158,
}

METRIC_QUERIES = {
    "server_measurement_count": "COUNT(*)",
    "average_cpu_utilization_pct": "AVG(sm.cpu_utilization_pct)",
    "average_memory_utilization_pct": "AVG(sm.memory_utilization_pct)",
    "average_disk_utilization_pct": "AVG(sm.disk_utilization_pct)",
    "average_server_network_utilization_pct": "AVG(sm.network_utilization_pct)",
}


def aggregate_reconciliation(connection: sqlite3.Connection) -> dict[str, object]:
    checks: dict[str, object] = {}
    for aggregate_column, expression in METRIC_QUERIES.items():
        difference = connection.execute(
            f"""WITH raw AS (
                SELECT s.facility_id,
                       CAST(substr(sm.timestamp, 1, 4) AS INTEGER) AS year,
                       {expression} AS value
                FROM server_metrics AS sm
                JOIN servers AS s ON s.server_id = sm.server_id
                GROUP BY s.facility_id, CAST(substr(sm.timestamp, 1, 4) AS INTEGER)
            )
            SELECT MAX(ABS(raw.value - aggregate.{aggregate_column}))
            FROM raw
            JOIN agg_facility_yearly AS aggregate USING (facility_id, year)"""
        ).fetchone()[0]
        checks[aggregate_column] = {"maximum_absolute_difference": difference}

    grouped_specs = {
        "power": (
            "power_metrics",
            "timestamp",
            {
                "power_measurement_count": "COUNT(*)",
                "average_pue": "AVG(pue)",
                "average_power_draw_kw": "AVG(power_draw_kw)",
                "average_it_load_kw": "AVG(it_load_kw)",
                "average_cooling_power_kw": "AVG(cooling_power_kw)",
                "total_cooling_cost": "SUM(cooling_cost)",
            },
        ),
        "network": (
            "network_metrics",
            "timestamp",
            {
                "network_measurement_count": "COUNT(*)",
                "average_bandwidth_utilization_pct": "AVG(bandwidth_utilization_pct)",
                "average_latency_ms": "AVG(latency_ms)",
                "average_packet_loss_pct": "AVG(packet_loss_pct)",
                "average_throughput_mbps": "AVG(throughput_mbps)",
                "average_network_availability_pct": "AVG(network_availability_pct)",
            },
        ),
        "incidents": (
            "uptime_incidents",
            "start_time",
            {
                "incident_count": "COUNT(*)",
                "total_downtime_minutes": "SUM(downtime_minutes)",
            },
        ),
    }
    for group, (table, date_column, metrics) in grouped_specs.items():
        group_results = {}
        for aggregate_column, expression in metrics.items():
            difference = connection.execute(
                f"""WITH raw AS (
                    SELECT facility_id,
                           CAST(substr({date_column}, 1, 4) AS INTEGER) AS year,
                           {expression} AS value
                    FROM {table}
                    GROUP BY facility_id, CAST(substr({date_column}, 1, 4) AS INTEGER)
                )
                SELECT MAX(ABS(raw.value - aggregate.{aggregate_column}))
                FROM raw
                JOIN agg_facility_yearly AS aggregate USING (facility_id, year)"""
            ).fetchone()[0]
            group_results[aggregate_column] = {
                "maximum_absolute_difference": difference
            }
        checks[group] = group_results

    aggregate_rows = connection.execute(
        "SELECT COUNT(*) FROM agg_facility_yearly"
    ).fetchone()[0]
    unique_rows = connection.execute(
        "SELECT COUNT(*) FROM (SELECT facility_id, year FROM agg_facility_yearly GROUP BY facility_id, year)"
    ).fetchone()[0]
    year_range = connection.execute(
        "SELECT MIN(year), MAX(year) FROM agg_facility_yearly"
    ).fetchone()
    zero_measurement_rows = connection.execute(
        """SELECT COUNT(*) FROM agg_facility_yearly
        WHERE server_measurement_count = 0
           OR power_measurement_count = 0
           OR network_measurement_count = 0"""
    ).fetchone()[0]
    maximum_difference = max(
        item["maximum_absolute_difference"] or 0
        for value in checks.values()
        for item in (value.values() if "maximum_absolute_difference" not in value else [value])
    )
    return {
        "grain": "one row per facility per calendar year",
        "row_count": aggregate_rows,
        "unique_grain_count": unique_rows,
        "year_min": year_range[0],
        "year_max": year_range[1],
        "rows_missing_core_measurements": zero_measurement_rows,
        "metric_checks": checks,
        "maximum_absolute_difference_across_metrics": maximum_difference,
        "all_metrics_identical": maximum_difference == 0,
    }


def benchmark_validation(before_path: Path, after_path: Path) -> dict[str, object]:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    before_queries = {query["id"]: query for query in before["queries"]}
    after_queries = {query["id"]: query for query in after["queries"]}
    comparisons = []
    for query_id in before_queries:
        raw = before_queries[query_id]
        optimized = after_queries[query_id]
        comparisons.append(
            {
                "id": query_id,
                "before_p50_ms": raw["p50_ms"],
                "after_p50_ms": optimized["p50_ms"],
                "p50_speedup": round(raw["p50_ms"] / optimized["p50_ms"], 1),
                "same_row_count": raw["row_count"] == optimized["row_count"],
                "same_result_sha256": raw["result_sha256"]
                == optimized["result_sha256"],
            }
        )
    return {
        "before": before["summary"],
        "after": after["summary"],
        "p50_speedup": round(
            before["summary"]["p50_ms"] / after["summary"]["p50_ms"], 1
        ),
        "p95_speedup": round(
            before["summary"]["p95_ms"] / after["summary"]["p95_ms"], 1
        ),
        "all_result_hashes_identical": all(
            comparison["same_result_sha256"] for comparison in comparisons
        ),
        "all_row_counts_identical": all(
            comparison["same_row_count"] for comparison in comparisons
        ),
        "queries": comparisons,
    }


def junit_summary(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    return {
        "tests": sum(int(suite.attrib.get("tests", 0)) for suite in suites),
        "failures": sum(int(suite.attrib.get("failures", 0)) for suite in suites),
        "errors": sum(int(suite.attrib.get("errors", 0)) for suite in suites),
        "skipped": sum(int(suite.attrib.get("skipped", 0)) for suite in suites),
        "time_seconds": round(
            sum(float(suite.attrib.get("time", 0)) for suite in suites), 3
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument(
        "--before", type=Path, default=Path("evaluation/results/sql_performance_before.json")
    )
    parser.add_argument(
        "--after", type=Path, default=Path("evaluation/results/sql_performance_after.json")
    )
    parser.add_argument(
        "--junit", type=Path, default=Path("evaluation/results/phase2_pytest.xml")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("evaluation/results/phase2_validation.json")
    )
    args = parser.parse_args()

    connection = sqlite3.connect(f"file:{args.database.resolve().as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only = ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_violations = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        raw_counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in RAW_COUNTS
        }
        aggregate = aggregate_reconciliation(connection)
        planner_stats = [
            {"table": row[0], "index": row[1], "stat": row[2]}
            for row in connection.execute(
                "SELECT tbl, idx, stat FROM sqlite_stat1 ORDER BY tbl, idx"
            )
        ]
    finally:
        connection.close()

    benchmark = benchmark_validation(args.before, args.after)
    regression = junit_summary(args.junit)
    checks = {
        "integrity_ok": integrity == "ok",
        "foreign_keys_ok": foreign_key_violations == 0,
        "canonical_row_counts_unchanged": raw_counts == RAW_COUNTS,
        "aggregate_grain_ok": aggregate["row_count"] == aggregate["unique_grain_count"] == 66,
        "aggregate_metrics_identical": aggregate["all_metrics_identical"],
        "benchmark_results_identical": benchmark["all_result_hashes_identical"]
        and benchmark["all_row_counts_identical"],
        "regression_suite_passed": regression["failures"] == regression["errors"] == 0,
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "database": {
            "sqlite_version": sqlite3.sqlite_version,
            "integrity_check": integrity,
            "foreign_key_violations": foreign_key_violations,
            "canonical_row_counts": raw_counts,
            "aggregate": aggregate,
            "planner_stats": planner_stats,
        },
        "benchmark": benchmark,
        "regression": regression,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "checks": checks,
        "benchmark": {
            "before": benchmark["before"],
            "after": benchmark["after"],
            "p50_speedup": benchmark["p50_speedup"],
            "p95_speedup": benchmark["p95_speedup"],
        },
        "regression": regression,
    }, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
