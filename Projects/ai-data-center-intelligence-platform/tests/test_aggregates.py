import sqlite3
from pathlib import Path

import pytest

from src.forecasting import METRICS, MetricForecaster


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


@pytest.fixture(scope="module")
def connection():
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    try:
        yield connection
    finally:
        connection.close()


def test_facility_yearly_aggregate_has_complete_unique_grain(connection):
    count, distinct_count = connection.execute(
        """SELECT COUNT(*), COUNT(DISTINCT facility_id || ':' || year)
        FROM agg_facility_yearly"""
    ).fetchone()
    assert count == 66
    assert distinct_count == count


@pytest.mark.parametrize(
    ("raw_expression", "aggregate_column"),
    [
        ("AVG(sm.cpu_utilization_pct)", "average_cpu_utilization_pct"),
        ("AVG(sm.memory_utilization_pct)", "average_memory_utilization_pct"),
        ("AVG(sm.disk_utilization_pct)", "average_disk_utilization_pct"),
        ("AVG(sm.network_utilization_pct)", "average_server_network_utilization_pct"),
    ],
)
def test_server_aggregates_reconcile_exactly(
    connection, raw_expression, aggregate_column
):
    maximum_difference = connection.execute(
        f"""WITH raw AS (
            SELECT s.facility_id,
                   CAST(substr(sm.timestamp, 1, 4) AS INTEGER) AS year,
                   {raw_expression} AS value
            FROM server_metrics AS sm
            JOIN servers AS s ON s.server_id = sm.server_id
            GROUP BY s.facility_id, CAST(substr(sm.timestamp, 1, 4) AS INTEGER)
        )
        SELECT MAX(ABS(raw.value - aggregate.{aggregate_column}))
        FROM raw
        JOIN agg_facility_yearly AS aggregate
          ON aggregate.facility_id = raw.facility_id
         AND aggregate.year = raw.year"""
    ).fetchone()[0]
    assert maximum_difference == pytest.approx(0.0, abs=1e-12)


def test_power_network_and_incident_aggregates_reconcile(connection):
    power_difference = connection.execute(
        """WITH raw AS (
            SELECT facility_id, CAST(substr(timestamp, 1, 4) AS INTEGER) AS year,
                   AVG(pue) AS average_pue, SUM(cooling_cost) AS total_cooling_cost
            FROM power_metrics GROUP BY facility_id, year
        )
        SELECT MAX(MAX(ABS(raw.average_pue - a.average_pue),
                       ABS(raw.total_cooling_cost - a.total_cooling_cost)))
        FROM raw JOIN agg_facility_yearly AS a USING (facility_id, year)"""
    ).fetchone()[0]
    network_difference = connection.execute(
        """WITH raw AS (
            SELECT facility_id, CAST(substr(timestamp, 1, 4) AS INTEGER) AS year,
                   AVG(latency_ms) AS average_latency_ms
            FROM network_metrics GROUP BY facility_id, year
        )
        SELECT MAX(ABS(raw.average_latency_ms - a.average_latency_ms))
        FROM raw JOIN agg_facility_yearly AS a USING (facility_id, year)"""
    ).fetchone()[0]
    incident_mismatches = connection.execute(
        """WITH raw AS (
            SELECT facility_id, CAST(substr(start_time, 1, 4) AS INTEGER) AS year,
                   COUNT(*) AS incident_count, SUM(downtime_minutes) AS downtime
            FROM uptime_incidents GROUP BY facility_id, year
        )
        SELECT COUNT(*) FROM raw
        JOIN agg_facility_yearly AS a USING (facility_id, year)
        WHERE raw.incident_count <> a.incident_count
           OR raw.downtime <> a.total_downtime_minutes"""
    ).fetchone()[0]
    assert power_difference == pytest.approx(0.0, abs=1e-12)
    assert network_difference == pytest.approx(0.0, abs=1e-12)
    assert incident_mismatches == 0


def test_forecaster_routes_annual_history_to_aggregate():
    spec = next(item for item in METRICS if item.key == "cpu_utilization_pct")
    history, sql = MetricForecaster(DATABASE).load_history(spec)
    assert len(history) == 66
    assert "agg_facility_yearly" in sql
    assert "server_metrics" not in sql


def test_raw_server_detail_still_uses_existing_composite_index(connection):
    plan = connection.execute(
        """EXPLAIN QUERY PLAN
        SELECT AVG(cpu_utilization_pct)
        FROM server_metrics
        WHERE server_id = 'SRV-00001'
          AND timestamp >= '2024-01-01'
          AND timestamp < '2025-01-01'"""
    ).fetchall()
    details = " ".join(row[3] for row in plan)
    assert "sqlite_autoindex_server_metrics_2" in details
