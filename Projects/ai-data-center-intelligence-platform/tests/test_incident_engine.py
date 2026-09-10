import sqlite3
from dataclasses import asdict
from pathlib import Path

import pytest

from src.incident_engine import IncidentTimelineEngine, RootCauseInvestigationEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


@pytest.fixture(scope="module")
def cooling_incident_id() -> str:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        return connection.execute(
            "SELECT incident_id FROM uptime_incidents WHERE root_cause='cooling failure' ORDER BY start_time LIMIT 1"
        ).fetchone()[0]


def test_timeline_reconstructs_only_sourced_events(cooling_incident_id) -> None:
    timeline = IncidentTimelineEngine(DATABASE).build(cooling_incident_id)
    source_types = {event.source_type for event in timeline.events}
    assert {"metric", "log", "incident", "maintenance"} <= source_types
    assert all(event.source_table and event.source_record_id for event in timeline.events)
    assert all(event.timestamp_precision in {"day", "minute"} for event in timeline.events)
    assert len([event for event in timeline.events if event.source_type == "log"]) >= 5


def test_timeline_source_ids_exist_in_database(cooling_incident_id) -> None:
    timeline = IncidentTimelineEngine(DATABASE).build(cooling_incident_id)
    id_columns = {
        "power_metrics": "metric_id",
        "network_metrics": "metric_id",
        "server_metrics": "metric_id",
        "system_logs": "log_id",
        "alerts": "alert_id",
        "uptime_incidents": "incident_id",
        "maintenance_actions": "action_id",
    }
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        for event in timeline.events:
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{event.source_table}" WHERE "{id_columns[event.source_table]}" = ?',
                (event.source_record_id,),
            ).fetchone()[0]
            assert count == 1, asdict(event)


def test_find_incidents_uses_facility_date_and_server_filters(cooling_incident_id) -> None:
    engine = IncidentTimelineEngine(DATABASE)
    timeline = engine.build(cooling_incident_id)
    incident = timeline.incident
    matches = engine.find_incidents(
        facility=incident["facility_name"],
        date=incident["start_time"][:10],
        server_id=incident["server_id"],
    )
    assert any(item["incident_id"] == cooling_incident_id for item in matches)


def test_investigation_uses_cautious_evidence_backed_language(cooling_incident_id) -> None:
    result = RootCauseInvestigationEngine(DATABASE, PROJECT_ROOT).investigate(cooling_incident_id)
    lower = result.answer.lower()
    assert result.recorded_root_cause == "cooling failure"
    assert "historical incident record classifies" in lower
    assert "decision support" in lower
    assert "not proof" in lower
    assert "definitely" not in lower
    assert result.diagnostic_confidence in {"Low", "Moderate", "High"}
    assert 0 <= result.confidence_score <= 9
    assert sum(result.confidence_breakdown.values()) == result.confidence_score


def test_investigation_exposes_complete_evidence_groups(cooling_incident_id) -> None:
    result = RootCauseInvestigationEngine(DATABASE, PROJECT_ROOT).investigate(cooling_incident_id)
    assert set(result.evidence) == {
        "metrics", "logs", "alerts", "incidents", "maintenance",
        "anomalies", "similar_incidents", "runbooks",
    }
    assert result.evidence["logs"]
    assert result.evidence["incidents"][0]["incident_id"] == cooling_incident_id
    assert result.evidence["maintenance"]
    assert result.evidence["similar_incidents"]
    assert result.evidence["runbooks"][0]["source"] == "knowledge/runbooks.yaml"
    assert result.recommended_checks


def test_unknown_incident_is_rejected() -> None:
    with pytest.raises(LookupError):
        IncidentTimelineEngine(DATABASE).build("INC-NOT-REAL")
