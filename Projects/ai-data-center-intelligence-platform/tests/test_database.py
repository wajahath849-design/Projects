import sqlite3
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"
EXPECTED_COUNTS = {
    "facilities": 6,
    "servers": 430,
    "server_metrics": 1_727_740,
    "power_metrics": 24_108,
    "network_metrics": 24_108,
    "uptime_incidents": 1_158,
}


@pytest.fixture(scope="module")
def connection():
    uri = f"file:{DATABASE.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        yield connection
    finally:
        connection.close()


def test_database_exists_and_is_readable(connection) -> None:
    assert DATABASE.exists()
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_row_counts(connection) -> None:
    actual = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in EXPECTED_COUNTS
    }
    assert actual == EXPECTED_COUNTS


def test_foreign_keys(connection) -> None:
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_analytical_views_exist(connection) -> None:
    names = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='view'")
    }
    assert names == {
        "vw_facility_daily_performance",
        "vw_monthly_energy_summary",
        "vw_server_utilization",
        "vw_incident_summary",
        "vw_facility_reliability",
    }


def test_daily_facility_view_has_complete_grain(connection) -> None:
    count = connection.execute("SELECT COUNT(*) FROM vw_facility_daily_performance").fetchone()[0]
    assert count == 24_108


def test_read_only_connection_blocks_writes(connection) -> None:
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("DELETE FROM facilities")

