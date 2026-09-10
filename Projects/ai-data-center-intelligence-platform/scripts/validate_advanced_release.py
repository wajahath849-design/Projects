"""Produce one machine-readable audit for the completed advanced release."""

from __future__ import annotations

import json
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "results"
DATABASE = ROOT / "database" / "datacenter.db"

EXPECTED_ROWS = {
    "facilities": 6,
    "servers": 430,
    "server_metrics": 1_727_740,
    "power_metrics": 24_108,
    "network_metrics": 24_108,
    "uptime_incidents": 1_158,
    "system_logs": 5_790,
    "alerts": 544,
    "maintenance_actions": 1_158,
    "detected_anomalies": 893,
    "incident_reviews": 6,
    "server_failure_risk": 430,
    "facility_health_scores": 6,
    "agg_facility_monthly_operations": 792,
    "agg_event_code_monthly": 5_065,
}


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def database_check() -> dict[str, object]:
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        rows = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in EXPECTED_ROWS
        }
    finally:
        connection.close()
    return {
        "passed": integrity == "ok" and foreign_keys == 0 and rows == EXPECTED_ROWS,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "row_counts": rows,
        "expected_row_counts": EXPECTED_ROWS,
    }


def pytest_check() -> dict[str, object]:
    suite = ET.parse(RESULTS / "phase_l_pytest.xml").getroot().find("testsuite")
    if suite is None:
        raise ValueError("No testsuite found in phase_l_pytest.xml")
    counts = {
        name: int(suite.attrib.get(name, 0))
        for name in ("tests", "failures", "errors", "skipped")
    }
    return {
        "passed": counts["tests"] >= 204 and counts["failures"] == 0 and counts["errors"] == 0,
        **counts,
        "seconds": float(suite.attrib.get("time", 0)),
    }


def power_bi_check() -> dict[str, object]:
    root = ROOT / "powerbi" / "PBI"
    project_name = "DataCenter Executive Dashboard"
    model = root / f"{project_name}.SemanticModel" / "definition"
    report = root / f"{project_name}.Report" / "definition"
    pages = load_json(report / "pages" / "pages.json")["pageOrder"]
    table_count = len(list((model / "tables").glob("*.tmdl")))
    relationships = (model / "relationships.tmdl").read_text(encoding="utf-8").count("relationship ")
    visuals = len(list((report / "pages").glob("*/visuals/*/visual.json")))
    measures = (model / "tables" / "_Measures.tmdl").read_text(encoding="utf-8").count("\n\tmeasure ")
    theme = (
        root
        / f"{project_name}.Report"
        / "StaticResources"
        / "RegisteredResources"
        / "DataCenterExecutive-20260904.json"
    )
    snapshots = {
        name: sum(1 for _ in (ROOT / "data" / "processed" / name).open(encoding="utf-8")) - 1
        for name in (
            "powerbi_cost_carbon_snapshot.csv",
            "powerbi_incident_impact_snapshot.csv",
            "powerbi_live_operations_snapshot.csv",
        )
    }
    return {
        "passed": len(pages) == 7
        and table_count == 17
        and relationships == 30
        and visuals == 223
        and measures == 56
        and theme.exists()
        and snapshots == {
            "powerbi_cost_carbon_snapshot.csv": 792,
            "powerbi_incident_impact_snapshot.csv": 1158,
            "powerbi_live_operations_snapshot.csv": 6,
        },
        "pages": len(pages),
        "semantic_tables": table_count,
        "relationships": relationships,
        "measures": measures,
        "visuals": visuals,
        "registered_theme": theme.name if theme.exists() else None,
        "snapshot_rows": snapshots,
        "desktop_render_review_required": True,
    }


def main() -> None:
    offline = load_json(RESULTS / "offline_baseline.json")
    kpis = load_json(ROOT / "docs" / "step6_kpi_validation.json")
    forecasts = load_json(ROOT / "docs" / "forecast_validation.json")
    root_cause = load_json(RESULTS / "root_cause_phase31.json")
    log_search = load_json(RESULTS / "log_search_phase28.json")
    rag = load_json(RESULTS / "rag_routing_phase29.json")
    performance = load_json(RESULTS / "performance_phase34_offline.json")
    advanced_simulation = load_json(RESULTS / "advanced_simulation_phase_l.json")
    advanced_performance = load_json(RESULTS / "advanced_performance_phase_l.json")
    cost_carbon = load_json(RESULTS / "cost_carbon_validation_phase_l.json")

    checks = {
        "database": database_check(),
        "pytest": pytest_check(),
        "offline_sql_security": {
            "passed": offline["security_passed"] == offline["security_cases"] == 10
            and offline["offline_sql_executed"] == offline["offline_sql_cases"] == 3,
            "security": f'{offline["security_passed"]}/{offline["security_cases"]}',
            "offline_sql": f'{offline["offline_sql_executed"]}/{offline["offline_sql_cases"]}',
        },
        "kpi_reconciliation": {
            "passed": bool(kpis["all_passed"]) and len(kpis["metrics"]) == 18,
            "metrics": len(kpis["metrics"]),
        },
        "forecast_coverage": {
            "passed": forecasts["metric_count"] == 16 and len(forecasts["results"]) == 16,
            "metrics": forecasts["metric_count"],
            "method": forecasts["method"],
        },
        "root_cause_evaluation": {
            "passed": root_cause["passed_cases"] == root_cause["case_count"] == 6
            and all(item["accuracy"] == 1.0 for item in root_cause["metrics"].values()),
            "cases": f'{root_cause["passed_cases"]}/{root_cause["case_count"]}',
            "truth_isolation": root_cause["truth_isolation"],
        },
        "advanced_simulation_evaluation": {
            "passed": advanced_simulation["passed_cases"] == advanced_simulation["case_count"] == 6
            and advanced_simulation["total_events_processed"] == 13008
            and all(
                item["passed"] == item["total"] == 6
                for item in advanced_simulation["metrics"].values()
            ),
            "cases": f'{advanced_simulation["passed_cases"]}/{advanced_simulation["case_count"]}',
            "events_processed": advanced_simulation["total_events_processed"],
            "truth_isolation": advanced_simulation["truth_isolation"],
        },
        "cost_carbon_reconciliation": {
            "passed": bool(cost_carbon["all_passed"])
            and len(cost_carbon["metrics"]) == 4
            and all(cost_carbon["checks"].values()),
            "reconciled_metrics": len(cost_carbon["metrics"]),
            "checks": len(cost_carbon["checks"]),
            "scope": cost_carbon["scope"],
        },
        "advanced_performance": {
            "passed": bool(advanced_performance["historical_database_unchanged"])
            and bool(advanced_performance["performance_regression_status"]["passed"]),
            "stream_events_per_second": advanced_performance["streaming"]["events_per_second"],
            "live_query_p95_ms": advanced_performance["streaming"]["current_query_p95_ms"],
            "multi_agent_p95_ms": advanced_performance["investigation"]["multi_p95_ms"],
            "historical_database_unchanged": advanced_performance["historical_database_unchanged"],
        },
        "log_index_benchmark": {
            "passed": all(
                log_search["after"][name]["p50_ms"] < log_search["before"][name]["p50_ms"]
                for name in ("global_time_window", "component_history", "severity_history")
            ),
            "before_after_p50_ms": {
                name: [log_search["before"][name]["p50_ms"], log_search["after"][name]["p50_ms"]]
                for name in ("global_time_window", "component_history", "severity_history")
            },
        },
        "rag_routing_benchmark": {
            "passed": rag["routed_p50_ms"] < rag["full_p50_ms"] and rag["mean_routing_precision"] >= 0.8,
            "full_p50_ms": rag["full_p50_ms"],
            "routed_p50_ms": rag["routed_p50_ms"],
            "mean_routing_precision": rag["mean_routing_precision"],
        },
        "offline_performance": {
            "passed": performance["question_count"] == 30
            and performance["summary"]["database_latency"]["p95_ms"] < 10,
            "questions": performance["question_count"],
            "total_p50_ms": performance["summary"]["total_latency"]["p50_ms"],
            "database_p95_ms": performance["summary"]["database_latency"]["p95_ms"],
            "scope": "offline regression; not a local-model accuracy benchmark",
        },
        "power_bi_source": power_bi_check(),
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "release": "operations-reliability-sustainability-phase-l",
        "all_passed": all(item["passed"] for item in checks.values()),
        "checks": checks,
        "caveats": [
            "All operational records are synthetic and model realistic data-center operations.",
            "Forecasts and scenarios are estimates, not observed future outcomes or guarantees.",
            "Recommendations never execute infrastructure changes and require human authorization.",
            "Power BI source is statically validated; final pixel review and PBIX export require Power BI Desktop.",
            "Full Ollama corpus accuracy depends on the locally installed model and is not claimed by this audit.",
        ],
    }
    target = RESULTS / "advanced_release_validation.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
