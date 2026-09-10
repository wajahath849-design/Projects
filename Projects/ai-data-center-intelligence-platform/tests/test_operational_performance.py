from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_operational_aggregate_sql_uses_summary_grain() -> None:
    sql = (PROJECT_ROOT / "database" / "operational_aggregates.sql").read_text(encoding="utf-8")
    assert "agg_facility_monthly_operations" in sql
    assert "agg_event_code_monthly" in sql
    assert "facility_months" in sql


def test_log_index_set_covers_supported_search_routes() -> None:
    sql = (PROJECT_ROOT / "database" / "operational_evidence.sql").read_text(encoding="utf-8")
    required = {
        "idx_logs_timestamp", "idx_logs_facility_timestamp", "idx_logs_server_timestamp",
        "idx_logs_event_timestamp", "idx_logs_component_timestamp", "idx_logs_level_timestamp",
    }
    assert all(name in sql for name in required)


def test_benchmark_compares_indexes_without_mutating_source() -> None:
    script = (PROJECT_ROOT / "scripts" / "benchmark_log_search.py").read_text(encoding="utf-8")
    assert 'sqlite3.connect(":memory:")' in script
    assert "mode=ro" in script
    assert "EXPLAIN QUERY PLAN" in script
