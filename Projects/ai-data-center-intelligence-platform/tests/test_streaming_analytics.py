import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.realtime.configuration import RealtimeConfig
from src.realtime.models import AlertEvent, TelemetryBatch, TelemetryEvent, utc_iso
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = PROJECT_ROOT / "database/datacenter.db"
SCHEMA = PROJECT_ROOT / "database/realtime_schema.sql"
CONFIG = PROJECT_ROOT / "config/realtime.yaml"
WEIGHTS = PROJECT_ROOT / "analytics/live_health_weights.yaml"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture()
def runtime(tmp_path: Path) -> tuple[RealtimeStore, StreamingAnalyticsService, str]:
    store = RealtimeStore(tmp_path / "realtime.db", CANONICAL, SCHEMA)
    store.initialize()
    session_id = store.create_session(simulation_session_id="SIM-STREAM")
    service = StreamingAnalyticsService(
        store, RealtimeConfig.from_yaml(CONFIG), WEIGHTS
    )
    return store, service, session_id


def metric(
    session_id: str,
    timestamp: datetime,
    name: str,
    value: float,
    unit: str,
    *,
    facility_id: str = "DC-FRA-01",
    server_id: str | None = None,
) -> TelemetryEvent:
    return TelemetryEvent.create(
        event_id=f"RTM-{uuid.uuid4().hex.upper()}",
        event_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        facility_id=facility_id,
        server_id=server_id,
        metric_name=name,
        metric_value=value,
        unit=unit,
        source="test_simulator",
        simulation_session_id=session_id,
    )


def test_rolling_statistics_and_state_versions_are_exact(runtime) -> None:
    store, service, session_id = runtime
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [1.30, 1.32, 1.34, 1.36, 1.38, 1.40, 1.42]
    for index, value in enumerate(values):
        service.process(TelemetryBatch(metrics=(
            metric(session_id, start + timedelta(seconds=index * 10), "pue", value, "ratio"),
        )))
    status = service.current_status(session_id, "DC-FRA-01")
    assert status.state_is_current is True
    assert status.event_version == status.state_version == len(values)
    windows = {
        int(row["window_minutes"]): row
        for row in status.rolling_statistics if row["metric_name"] == "pue"
    }
    assert set(windows) == {1, 5, 15}
    assert windows[1]["sample_count"] == 7
    assert windows[1]["mean_value"] == pytest.approx(sum(values) / len(values))
    assert windows[1]["change_rate_per_minute"] == pytest.approx(0.12)
    assert windows[1]["last_value"] == pytest.approx(1.42)
    assert len(status.metrics) == 1


def test_event_version_exposes_unprocessed_state(runtime) -> None:
    store, service, session_id = runtime
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.ingest_batch(TelemetryBatch(metrics=(
        metric(session_id, timestamp, "pue", 1.4, "ratio"),
    )))
    status = service.current_status(session_id)
    assert status.event_version == 1
    assert status.state_version == 0
    assert status.state_is_current is False


def test_online_anomaly_contains_grounded_baseline_evidence(runtime) -> None:
    _, service, session_id = runtime
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    server_id = "SRV-00001"
    for index, value in enumerate([50.0, 50.5, 49.5, 50.2, 49.8]):
        service.process(TelemetryBatch(metrics=(
            metric(
                session_id, start + timedelta(minutes=index),
                "cpu_utilization_pct", value, "percent", server_id=server_id,
            ),
        )))
    result = service.process(TelemetryBatch(metrics=(
        metric(
            session_id, start + timedelta(minutes=5),
            "cpu_utilization_pct", 99.0, "percent", server_id=server_id,
        ),
    )))
    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.metric_name == "cpu_utilization_pct"
    assert anomaly.severity == "critical"
    assert "rolling_zscore" in anomaly.detection_method
    evidence = json.loads(anomaly.evidence_json)
    assert evidence["baseline_sample_count"] == 5
    assert evidence["event_id"] == anomaly.event_id
    status = service.current_status(session_id, "DC-FRA-01")
    assert len(status.active_anomalies) == 1


def test_live_health_degrades_from_observed_bad_signals(runtime) -> None:
    store, service, session_id = runtime
    simulator = TelemetrySimulator(
        CANONICAL, random_seed=11, tick_interval_seconds=5,
        server_sample_size_per_facility=1,
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service.process(simulator.generate_tick(session_id, start))
    baseline = service.current_status(session_id, "DC-FRA-01").facility_health[0]
    alert = AlertEvent(
        alert_id="RTA-HEALTH-ALERT",
        event_timestamp=utc_iso(start + timedelta(seconds=5)),
        ingestion_timestamp=utc_iso(start + timedelta(seconds=5)),
        facility_id="DC-FRA-01",
        server_id=None,
        metric_name="pue",
        severity="critical",
        observed_value=2.3,
        threshold_value=1.8,
        status="active",
        source="test_simulator",
        quality_flag="valid",
        simulation_session_id=session_id,
        evidence={"synthetic": True},
    )
    bad_metrics = (
        metric(session_id, start + timedelta(seconds=5), "pue", 2.3, "ratio"),
        metric(session_id, start + timedelta(seconds=5), "latency_ms", 120, "ms"),
        metric(session_id, start + timedelta(seconds=5), "packet_loss_pct", 8, "percent"),
        metric(session_id, start + timedelta(seconds=5), "network_availability_pct", 94, "percent"),
        metric(session_id, start + timedelta(seconds=5), "availability_pct", 95, "percent"),
        metric(session_id, start + timedelta(seconds=5), "downtime_minutes", 3, "minutes"),
        metric(session_id, start + timedelta(seconds=5), "incident_indicator", 1, "state"),
        metric(
            session_id, start + timedelta(seconds=5), "cpu_utilization_pct", 99,
            "percent", server_id="SRV-00001",
        ),
        metric(
            session_id, start + timedelta(seconds=5), "temperature_c", 95,
            "celsius", server_id="SRV-00001",
        ),
    )
    service.process(TelemetryBatch(metrics=bad_metrics, alerts=(alert,)))
    degraded = service.current_status(session_id, "DC-FRA-01").facility_health[0]
    assert float(degraded["health_score"]) < float(baseline["health_score"])
    assert degraded["active_alert_count"] == 1
    assert degraded["active_anomaly_count"] >= 1
    drivers = json.loads(str(degraded["drivers_json"]))
    components = {driver["component"] for driver in drivers}
    assert {"energy_efficiency", "network_health", "alert_burden"} <= components
    assert degraded["data_completeness_pct"] == 100.0


def test_streaming_processing_never_changes_canonical_history(runtime) -> None:
    _, service, session_id = runtime
    before = digest(CANONICAL)
    simulator = TelemetrySimulator(CANONICAL, server_sample_size_per_facility=1)
    service.process(
        simulator.generate_tick(session_id, datetime(2026, 1, 1, tzinfo=timezone.utc))
    )
    assert digest(CANONICAL) == before
