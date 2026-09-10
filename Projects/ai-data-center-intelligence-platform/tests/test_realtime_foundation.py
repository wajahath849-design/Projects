import hashlib
import queue
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.realtime.models import TelemetryBatch, TelemetryEvent
from src.realtime.simulator import BufferedTelemetryStream, TelemetrySimulator
from src.realtime.store import RealtimeStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = PROJECT_ROOT / "database/datacenter.db"
SCHEMA = PROJECT_ROOT / "database/realtime_schema.sql"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture()
def store(tmp_path: Path) -> RealtimeStore:
    result = RealtimeStore(tmp_path / "realtime.db", CANONICAL, SCHEMA)
    result.initialize()
    return result


def test_event_model_requires_governed_units_scope_and_finite_values() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    event = TelemetryEvent.create(
        event_timestamp=timestamp,
        facility_id="DC-FRA-01",
        server_id="SRV-0001",
        metric_name="cpu_utilization_pct",
        metric_value=42,
        unit="percent",
        source="simulator",
        simulation_session_id="SIM-TEST",
    )
    assert event.metric_value == 42
    assert event.event_timestamp.endswith("+00:00")
    with pytest.raises(ValueError, match="requires server_id"):
        TelemetryEvent.create(
            event_timestamp=timestamp, facility_id="DC-FRA-01",
            metric_name="cpu_utilization_pct", metric_value=42, unit="percent",
            source="simulator", simulation_session_id="SIM-TEST",
        )
    with pytest.raises(ValueError, match="requires unit"):
        TelemetryEvent.create(
            event_timestamp=timestamp, facility_id="DC-FRA-01",
            metric_name="pue", metric_value=1.5, unit="percent",
            source="simulator", simulation_session_id="SIM-TEST",
        )
    with pytest.raises(ValueError, match="finite"):
        TelemetryEvent.create(
            event_timestamp=timestamp, facility_id="DC-FRA-01",
            metric_name="pue", metric_value=float("nan"), unit="ratio",
            source="simulator", simulation_session_id="SIM-TEST",
        )


def test_store_is_separate_validates_inventory_and_preserves_history(store: RealtimeStore) -> None:
    before = digest(CANONICAL)
    session_id = store.create_session(simulation_session_id="SIM-FOUNDATION")
    event = TelemetryEvent.create(
        event_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        facility_id="DC-FRA-01", metric_name="pue", metric_value=1.45,
        unit="ratio", source="simulator", simulation_session_id=session_id,
    )
    result = store.ingest_batch(TelemetryBatch(metrics=(event,)))
    assert result.total_inserted == 1
    assert result.retained_metric_events == 1
    with store.read_connection() as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM realtime_metric_events").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM realtime_metric_events")
    assert digest(CANONICAL) == before

    invalid = TelemetryEvent.create(
        event_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        facility_id="FAC-999", metric_name="pue", metric_value=1.45,
        unit="ratio", source="simulator", simulation_session_id=session_id,
    )
    with pytest.raises(ValueError, match="Unknown canonical facility"):
        store.ingest_batch(TelemetryBatch(metrics=(invalid,)))


def test_simulator_covers_server_facility_network_and_reliability(store: RealtimeStore) -> None:
    session_id = store.create_session(simulation_session_id="SIM-COVERAGE")
    simulator = TelemetrySimulator(
        CANONICAL, random_seed=7, tick_interval_seconds=5,
        server_sample_size_per_facility=1,
    )
    batch = simulator.generate_tick(
        session_id, datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    names = {event.metric_name for event in batch.metrics}
    assert {
        "cpu_utilization_pct", "memory_utilization_pct", "disk_utilization_pct",
        "temperature_c", "server_status", "power_draw_kw", "it_load_kw",
        "cooling_power_kw", "pue", "energy_consumption_kwh", "latency_ms",
        "throughput_mbps", "packet_loss_pct", "availability_pct",
        "active_alert_count", "incident_indicator",
    } <= names
    result = store.ingest_batch(batch)
    assert result.metrics_inserted == len(batch.metrics)
    assert {event.facility_id for event in batch.metrics} == {
        "DC-DUB-01", "DC-FRA-01", "DC-IAD-01", "DC-PDX-01",
        "DC-SIN-01", "DC-SYD-01",
    }
    for event in batch.metrics:
        if event.metric_name == "energy_consumption_kwh":
            assert event.metadata["synthetic"] is True


def test_retention_and_count_limits_are_enforced_per_session(store: RealtimeStore) -> None:
    session_id = store.create_session(
        simulation_session_id="SIM-RETENTION", retention_hours=1, max_events=3
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = tuple(
        TelemetryEvent.create(
            event_id=f"RTM-RETENTION-{index}",
            event_timestamp=start + timedelta(minutes=30 * index),
            ingestion_timestamp=start + timedelta(minutes=30 * index),
            facility_id="DC-FRA-01", metric_name="pue", metric_value=1.4,
            unit="ratio", source="simulator", simulation_session_id=session_id,
        )
        for index in range(5)
    )
    result = store.ingest_batch(TelemetryBatch(metrics=events))
    assert result.retained_metric_events == 3
    with store.read_connection() as connection:
        timestamps = [
            row[0] for row in connection.execute(
                "SELECT event_timestamp FROM realtime_metric_events ORDER BY event_timestamp"
            )
        ]
    assert timestamps == [events[2].event_timestamp, events[3].event_timestamp, events[4].event_timestamp]


def test_bounded_stream_applies_backpressure_and_drains(store: RealtimeStore) -> None:
    session_id = store.create_session(simulation_session_id="SIM-QUEUE")
    simulator = TelemetrySimulator(CANONICAL, server_sample_size_per_facility=0)
    stream = BufferedTelemetryStream(max_batches=1)
    first = simulator.generate_tick(session_id, datetime(2026, 1, 1, tzinfo=timezone.utc))
    stream.publish(first)
    with pytest.raises(queue.Full):
        stream.publish(first, timeout_seconds=0)
    results = stream.drain(store)
    assert len(results) == 1
    assert stream.pending_batches == 0
