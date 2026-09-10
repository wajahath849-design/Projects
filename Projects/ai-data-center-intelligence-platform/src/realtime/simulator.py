"""Deterministic synthetic telemetry generator and bounded event buffer."""

from __future__ import annotations

import queue
import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypeVar

from src.database import connect_read_only
from src.realtime.models import LogEvent, TelemetryBatch, TelemetryEvent, utc_iso
from src.realtime.store import IngestionResult, RealtimeStore


_EVENT_NAMESPACE = uuid.UUID("017b3f1b-581a-47ab-b816-fb7adf131c03")
_ResultT = TypeVar("_ResultT")


@dataclass(frozen=True)
class FacilityBaseline:
    facility_id: str
    power_draw_kw: float
    it_load_kw: float
    cooling_power_kw: float
    pue: float
    bandwidth_utilization_pct: float
    latency_ms: float
    packet_loss_pct: float
    throughput_mbps: float
    network_availability_pct: float


class TelemetrySimulator:
    """Generate reproducible live observations anchored to canonical history."""

    def __init__(
        self,
        canonical_database_path: Path | str,
        *,
        random_seed: int = 2026,
        tick_interval_seconds: float = 5.0,
        server_sample_size_per_facility: int = 3,
    ) -> None:
        if tick_interval_seconds <= 0:
            raise ValueError("Tick interval must be positive")
        if server_sample_size_per_facility < 0:
            raise ValueError("Server sample size cannot be negative")
        self.database_path = Path(canonical_database_path)
        self.random = random.Random(random_seed)
        self.tick_interval_seconds = float(tick_interval_seconds)
        self.server_sample_size_per_facility = server_sample_size_per_facility
        self.baselines, self.servers = self._load_baselines()

    def _load_baselines(self) -> tuple[list[FacilityBaseline], dict[str, list[dict[str, float | str]]]]:
        with connect_read_only(self.database_path) as connection:
            latest_year = connection.execute(
                "SELECT MAX(substr(timestamp, 1, 4)) FROM power_metrics"
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT p.facility_id,
                    AVG(p.power_draw_kw) AS power_draw_kw,
                    AVG(p.it_load_kw) AS it_load_kw,
                    AVG(p.cooling_power_kw) AS cooling_power_kw,
                    AVG(p.pue) AS pue,
                    AVG(n.bandwidth_utilization_pct) AS bandwidth_utilization_pct,
                    AVG(n.latency_ms) AS latency_ms,
                    AVG(n.packet_loss_pct) AS packet_loss_pct,
                    AVG(n.throughput_mbps) AS throughput_mbps,
                    AVG(n.network_availability_pct) AS network_availability_pct
                FROM power_metrics AS p
                JOIN network_metrics AS n
                  ON n.facility_id=p.facility_id AND n.timestamp=p.timestamp
                WHERE substr(p.timestamp, 1, 4)=?
                GROUP BY p.facility_id ORDER BY p.facility_id""",
                (latest_year,),
            ).fetchall()
            baselines = [FacilityBaseline(**dict(row)) for row in rows]
            latest_date = connection.execute(
                "SELECT MAX(timestamp) FROM server_metrics"
            ).fetchone()[0]
            server_rows = connection.execute(
                """SELECT s.facility_id, s.server_id,
                    m.cpu_utilization_pct, m.memory_utilization_pct,
                    m.disk_utilization_pct, m.network_utilization_pct
                FROM servers AS s
                JOIN server_metrics AS m ON m.server_id=s.server_id
                WHERE m.timestamp=? AND s.status='active'
                ORDER BY s.facility_id, s.server_id""",
                (latest_date,),
            ).fetchall()
        servers: dict[str, list[dict[str, float | str]]] = {}
        for row in server_rows:
            servers.setdefault(row["facility_id"], []).append(dict(row))
        return baselines, servers

    @staticmethod
    def _event_id(session_id: str, timestamp: str, scope: str, metric: str) -> str:
        value = uuid.uuid5(_EVENT_NAMESPACE, f"{session_id}|{timestamp}|{scope}|{metric}")
        return f"RTM-{value.hex.upper()}"

    def _metric(
        self,
        session_id: str,
        timestamp: str,
        facility_id: str,
        metric_name: str,
        value: float,
        unit: str,
        server_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> TelemetryEvent:
        scope = server_id or facility_id
        return TelemetryEvent.create(
            event_id=self._event_id(session_id, timestamp, scope, metric_name),
            event_timestamp=timestamp,
            ingestion_timestamp=timestamp,
            facility_id=facility_id,
            server_id=server_id,
            metric_name=metric_name,
            metric_value=round(value, 6),
            unit=unit,
            source="simulator",
            simulation_session_id=session_id,
            metadata={"synthetic": True, **(metadata or {})},
        )

    def generate_tick(
        self,
        simulation_session_id: str,
        event_timestamp: datetime | str | None = None,
    ) -> TelemetryBatch:
        timestamp = utc_iso(event_timestamp or datetime.now(timezone.utc))
        metrics: list[TelemetryEvent] = []
        for baseline in self.baselines:
            facility_id = baseline.facility_id
            it_load = max(0.0, baseline.it_load_kw * self.random.uniform(0.985, 1.015))
            pue = min(5.0, max(1.0, baseline.pue + self.random.gauss(0, 0.008)))
            cooling = max(0.0, it_load * (pue - 1.0))
            total_power = it_load + cooling
            facility_values = (
                ("it_load_kw", it_load, "kW"),
                ("cooling_power_kw", cooling, "kW"),
                ("power_draw_kw", total_power, "kW"),
                ("pue", pue, "ratio"),
                (
                    "energy_consumption_kwh",
                    total_power * self.tick_interval_seconds / 3600.0,
                    "kWh",
                ),
                (
                    "bandwidth_utilization_pct",
                    min(100.0, max(0.0, baseline.bandwidth_utilization_pct + self.random.gauss(0, 1))),
                    "percent",
                ),
                ("latency_ms", max(0.0, baseline.latency_ms + self.random.gauss(0, 0.25)), "ms"),
                ("packet_loss_pct", max(0.0, baseline.packet_loss_pct + self.random.gauss(0, 0.02)), "percent"),
                ("throughput_mbps", max(0.0, baseline.throughput_mbps * self.random.uniform(0.98, 1.02)), "Mbps"),
                (
                    "network_availability_pct",
                    min(100.0, max(0.0, baseline.network_availability_pct + self.random.gauss(0, 0.005))),
                    "percent",
                ),
                ("availability_pct", 100.0, "percent"),
                ("downtime_minutes", 0.0, "minutes"),
                ("active_alert_count", 0.0, "count"),
                ("incident_indicator", 0.0, "state"),
            )
            metrics.extend(
                self._metric(
                    simulation_session_id, timestamp, facility_id,
                    name, value, unit,
                    metadata={"baseline_source": "canonical_latest_complete_year_average"},
                )
                for name, value, unit in facility_values
            )
            candidates = self.servers.get(facility_id, [])
            sample_size = min(self.server_sample_size_per_facility, len(candidates))
            for server in candidates[:sample_size]:
                server_id = str(server["server_id"])
                cpu = min(100.0, max(0.0, float(server["cpu_utilization_pct"]) + self.random.gauss(0, 1.5)))
                memory = min(100.0, max(0.0, float(server["memory_utilization_pct"]) + self.random.gauss(0, 1.0)))
                disk = min(100.0, max(0.0, float(server["disk_utilization_pct"]) + self.random.gauss(0, 0.25)))
                network = min(100.0, max(0.0, float(server["network_utilization_pct"]) + self.random.gauss(0, 1.5)))
                temperature = min(150.0, max(-20.0, 28.0 + 0.42 * cpu + self.random.gauss(0, 0.5)))
                for name, value, unit in (
                    ("cpu_utilization_pct", cpu, "percent"),
                    ("memory_utilization_pct", memory, "percent"),
                    ("disk_utilization_pct", disk, "percent"),
                    ("network_utilization_pct", network, "percent"),
                    ("temperature_c", temperature, "celsius"),
                    ("server_status", 1.0, "state"),
                ):
                    metrics.append(self._metric(
                        simulation_session_id, timestamp, facility_id,
                        name, value, unit, server_id,
                        {"baseline_source": "canonical_latest_server_observation"},
                    ))
        return TelemetryBatch(metrics=tuple(metrics))

    def generate_restart(
        self,
        simulation_session_id: str,
        facility_id: str,
        server_id: str,
        event_timestamp: datetime | str | None = None,
    ) -> TelemetryBatch:
        timestamp = utc_iso(event_timestamp or datetime.now(timezone.utc))
        metric = self._metric(
            simulation_session_id, timestamp, facility_id,
            "server_status", 0.0, "state", server_id,
            {"status_label": "restarting"},
        )
        log = LogEvent(
            event_id=f"RTL-{uuid.uuid4().hex.upper()}",
            event_timestamp=timestamp,
            ingestion_timestamp=timestamp,
            facility_id=facility_id,
            server_id=server_id,
            level="warning",
            component="server_runtime",
            event_code="SERVER_RESTART",
            message="Synthetic server restart observed.",
            source="simulator",
            quality_flag="valid",
            simulation_session_id=simulation_session_id,
            metadata={"synthetic": True},
        )
        return TelemetryBatch(metrics=(metric,), logs=(log,))


class BufferedTelemetryStream:
    """Bounded local queue with explicit backpressure and batch draining."""

    def __init__(self, max_batches: int = 100) -> None:
        if max_batches < 1:
            raise ValueError("Queue size must be positive")
        self._queue: queue.Queue[TelemetryBatch] = queue.Queue(maxsize=max_batches)

    @property
    def pending_batches(self) -> int:
        return self._queue.qsize()

    def publish(self, batch: TelemetryBatch, timeout_seconds: float = 1.0) -> None:
        if batch.event_count == 0:
            raise ValueError("Cannot publish an empty batch")
        self._queue.put(batch, timeout=max(0.0, timeout_seconds))

    def drain(self, store: RealtimeStore, max_batches: int = 10) -> list[IngestionResult]:
        return self.drain_with(store.ingest_batch, max_batches=max_batches)

    def drain_with(
        self,
        processor: Callable[[TelemetryBatch], _ResultT],
        max_batches: int = 10,
    ) -> list[_ResultT]:
        """Drain through a storage or streaming-analytics processor."""
        results: list[_ResultT] = []
        for _ in range(max(0, max_batches)):
            try:
                batch = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                results.append(processor(batch))
            finally:
                self._queue.task_done()
        return results


def run_simulation_ticks(
    simulator: TelemetrySimulator,
    stream: BufferedTelemetryStream,
    store: RealtimeStore,
    session_id: str,
    *,
    ticks: int,
    speed_multiplier: float = 1.0,
    start_time: datetime | None = None,
) -> list[IngestionResult]:
    """Run a finite or CLI-controlled telemetry loop without UI coupling."""
    if ticks < 1 or speed_multiplier <= 0:
        raise ValueError("Ticks and speed multiplier must be positive")
    current = start_time or datetime.now(timezone.utc)
    results: list[IngestionResult] = []
    for index in range(ticks):
        stream.publish(simulator.generate_tick(session_id, current))
        results.extend(stream.drain(store))
        current += timedelta(seconds=simulator.tick_interval_seconds)
        if index < ticks - 1:
            time.sleep(simulator.tick_interval_seconds / speed_multiplier)
    return results
