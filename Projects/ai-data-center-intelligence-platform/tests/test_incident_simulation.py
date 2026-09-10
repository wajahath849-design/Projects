from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.realtime.configuration import RealtimeConfig
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.simulation.lab import IncidentSimulationLab


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def lab(tmp_path: Path) -> IncidentSimulationLab:
    store = RealtimeStore(
        tmp_path / "realtime.db", ROOT / "database/datacenter.db",
        ROOT / "database/realtime_schema.sql",
    )
    store.initialize()
    config = RealtimeConfig.from_yaml(ROOT / "config/realtime.yaml")
    simulator = TelemetrySimulator(
        ROOT / "database/datacenter.db", random_seed=8,
        tick_interval_seconds=config.tick_interval_seconds,
        server_sample_size_per_facility=1,
    )
    analytics = StreamingAnalyticsService(
        store, config, ROOT / "analytics/live_health_weights.yaml"
    )
    return IncidentSimulationLab(
        store, simulator, analytics, ROOT / "config/simulation_scenarios.yaml"
    )


def test_catalog_contains_all_six_required_scenarios_without_truth(lab: IncidentSimulationLab) -> None:
    keys = {row["scenario_key"] for row in lab.catalog()}
    assert keys == {
        "cooling_degradation", "network_congestion", "server_overload",
        "power_instability", "storage_pressure", "cascading_failure",
    }
    assert "root_cause" not in str(lab.catalog()).lower()


def test_controls_provenance_and_replay_are_deterministic(lab: IncidentSimulationLab) -> None:
    session = lab.start(
        "cooling_degradation", facility_id="DC-FRA-01",
        simulation_session_id="SIM-LAB", started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    first = lab.advance(session)
    first_values = [(event.event_id, event.metric_value) for event in first.batch.metrics]
    assert all("simulation_provenance" in event.metadata for event in first.batch.metrics)
    lab.pause(session)
    with pytest.raises(RuntimeError, match="running"):
        lab.advance(session)
    lab.set_speed(session, 5)
    lab.replay(session)
    replay = lab.advance(session)
    assert [(event.event_id, event.metric_value) for event in replay.batch.metrics] == first_values
    assert lab.store.session_versions(session) == (1, 1)


def test_scenario_degrades_and_then_recovers_with_observable_events(lab: IncidentSimulationLab) -> None:
    session = lab.start(
        "cascading_failure", facility_id="DC-FRA-01",
        simulation_session_id="SIM-CASCADE", started_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    steps = lab.run_to_completion(session)
    pue = [
        next(event.metric_value for event in step.batch.metrics
             if event.facility_id == "DC-FRA-01" and event.metric_name == "pue")
        for step in steps
    ]
    assert max(pue) > pue[0]
    assert pue[-1] < max(pue)
    assert any(step.batch.logs for step in steps)
    assert any(step.batch.alerts for step in steps)
    assert any(step.batch.incidents for step in steps)
    assert lab.store.session_row(session)["status"] == "completed"
