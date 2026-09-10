import sqlite3
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


@pytest.fixture(scope="module")
def connection():
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    try:
        yield connection
    finally:
        connection.close()


def test_evidence_counts_and_referential_integrity(connection) -> None:
    assert connection.execute("SELECT COUNT(*) FROM system_logs").fetchone()[0] == 5_790
    assert connection.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 544
    assert connection.execute("SELECT COUNT(*) FROM maintenance_actions").fetchone()[0] == 1_158
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_each_incident_has_exactly_one_consistent_resolution(connection) -> None:
    mismatches = connection.execute(
        """SELECT COUNT(*)
        FROM maintenance_actions AS a
        JOIN uptime_incidents AS i ON i.incident_id = a.incident_id
        WHERE a.facility_id <> i.facility_id
           OR a.server_id <> i.server_id
           OR datetime(a.timestamp) <> datetime(i.end_time)"""
    ).fetchone()[0]
    distinct_incidents = connection.execute(
        "SELECT COUNT(DISTINCT incident_id) FROM maintenance_actions"
    ).fetchone()[0]
    assert mismatches == 0
    assert distinct_incidents == 1_158


def test_incident_windows_have_generated_log_evidence(connection) -> None:
    missing = connection.execute(
        """SELECT COUNT(*) FROM uptime_incidents AS i
        WHERE NOT EXISTS (
            SELECT 1 FROM system_logs AS l
            WHERE l.facility_id = i.facility_id
              AND l.server_id = i.server_id
              AND datetime(l.timestamp) BETWEEN datetime(i.start_time, '-15 minutes')
                                            AND datetime(i.end_time)
        )"""
    ).fetchone()[0]
    assert missing == 0


def test_logs_match_server_inventory_rack(connection) -> None:
    mismatches = connection.execute(
        """SELECT COUNT(*)
        FROM system_logs AS l
        JOIN servers AS s ON s.server_id = l.server_id
        WHERE l.facility_id <> s.facility_id OR l.rack_id <> s.rack_id"""
    ).fetchone()[0]
    assert mismatches == 0


def test_alerts_are_threshold_grounded_and_resolved_in_time(connection) -> None:
    invalid = connection.execute(
        """SELECT COUNT(*) FROM alerts
        WHERE observed_value < threshold_value
           OR status <> 'resolved'
           OR resolved_at IS NULL
           OR datetime(resolved_at) < datetime(timestamp)"""
    ).fetchone()[0]
    assert invalid == 0


def test_evidence_text_is_treated_as_data_not_instructions(connection) -> None:
    suspicious = connection.execute(
        """SELECT COUNT(*) FROM system_logs
        WHERE lower(message) LIKE '%ignore previous%'
           OR lower(message) LIKE '%system prompt%'
           OR lower(message) LIKE '%execute sql%'"""
    ).fetchone()[0]
    assert suspicious == 0


def test_operational_search_indexes_exist(connection) -> None:
    indexes = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
    }
    assert {
        "idx_logs_facility_timestamp",
        "idx_logs_server_timestamp",
        "idx_logs_event_timestamp",
        "idx_alerts_facility_timestamp",
        "idx_alerts_server_timestamp",
        "idx_alerts_status_severity",
        "idx_actions_incident_timestamp",
        "idx_actions_facility_timestamp",
    } <= indexes
