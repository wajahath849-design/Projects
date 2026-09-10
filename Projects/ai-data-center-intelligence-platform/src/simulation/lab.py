"""Deterministic incident injection with pause, reset and replay controls."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.realtime.models import (
    METRIC_DEFINITIONS,
    AlertEvent,
    IncidentEvent,
    LogEvent,
    TelemetryBatch,
    TelemetryEvent,
    utc_iso,
)
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsResult, StreamingAnalyticsService


_LAB_NAMESPACE = uuid.UUID("0c595266-6962-46dc-81f5-84dc5ce9cabe")


@dataclass(frozen=True)
class SimulationStep:
    simulation_session_id: str
    scenario_key: str
    tick_index: int
    phase: str
    progress: float
    batch: TelemetryBatch
    analytics: StreamingAnalyticsResult


class IncidentSimulationLab:
    """Run observable failure scenarios without exposing evaluation truth."""

    ALLOWED_SPEEDS = frozenset({1.0, 2.0, 5.0, 10.0})

    def __init__(
        self,
        store: RealtimeStore,
        simulator: TelemetrySimulator,
        analytics: StreamingAnalyticsService,
        scenario_config_path: Path | str,
    ) -> None:
        self.store = store
        self.simulator = simulator
        self.analytics = analytics
        payload = yaml.safe_load(Path(scenario_config_path).read_text(encoding="utf-8"))
        self.version = str(payload["version"])
        self.default_duration_ticks = int(payload["default_duration_ticks"])
        self.scenarios = dict(payload["scenarios"])
        self._positions: dict[str, int] = {}
        self._random_states: dict[str, object] = {}

    def catalog(self) -> list[dict[str, object]]:
        """Return operator-safe scenario metadata, not hidden evaluation answers."""
        return [
            {
                "scenario_key": key,
                "title": value["title"],
                "complexity": value["complexity"],
                "duration_ticks": self.default_duration_ticks,
            }
            for key, value in self.scenarios.items()
        ]

    def start(
        self,
        scenario_key: str,
        *,
        facility_id: str,
        speed_multiplier: float = 1.0,
        random_seed: int = 2026,
        simulation_session_id: str | None = None,
        started_at: datetime | str | None = None,
    ) -> str:
        if scenario_key not in self.scenarios:
            raise ValueError("Unknown incident scenario")
        if speed_multiplier not in self.ALLOWED_SPEEDS:
            raise ValueError("Simulation speed must be one of 1x, 2x, 5x or 10x")
        if facility_id not in self.store._facilities:
            raise ValueError("Unknown canonical facility")
        session_id = self.store.create_session(
            scenario_name=scenario_key,
            speed_multiplier=speed_multiplier,
            random_seed=random_seed,
            simulation_session_id=simulation_session_id,
            started_at=started_at,
            metadata={
                "synthetic": True,
                "lab_version": self.version,
                "target_facility_id": facility_id,
                "ground_truth_available_to_runtime": False,
            },
        )
        self._positions[session_id] = 0
        self._random_states[session_id] = self.simulator.random.getstate()
        return session_id

    def pause(self, session_id: str) -> None:
        self.store.set_session_status(session_id, "paused")

    def resume(self, session_id: str) -> None:
        self.store.set_session_status(session_id, "running")

    def set_speed(self, session_id: str, speed_multiplier: float) -> None:
        self.store.set_session_speed(session_id, speed_multiplier)

    def reset(self, session_id: str) -> None:
        self.store.reset_session(session_id)
        self._positions[session_id] = 0

    def replay(self, session_id: str) -> None:
        self.reset(session_id)
        state = self._random_states.get(session_id)
        if state is not None:
            self.simulator.random.setstate(state)
        self.resume(session_id)

    def advance(self, session_id: str) -> SimulationStep:
        session = self.store.session_row(session_id)
        if session["status"] != "running":
            raise RuntimeError("Simulation must be running before it can advance")
        scenario_key = str(session["scenario_name"])
        scenario = self.scenarios[scenario_key]
        tick_index = self._positions.get(session_id, 0)
        if tick_index >= self.default_duration_ticks:
            raise RuntimeError("Simulation has completed; replay or reset it")
        started_at = datetime.fromisoformat(str(session["started_at"]))
        timestamp = started_at + timedelta(
            seconds=tick_index * self.simulator.tick_interval_seconds
        )
        baseline = self.simulator.generate_tick(session_id, timestamp)
        facility_id = yaml.safe_load(str(session["metadata_json"]))["target_facility_id"]
        batch, progress, phase = self._inject(
            baseline, scenario, facility_id, scenario_key, tick_index, timestamp
        )
        analytics_result = self.analytics.process(batch)
        self._positions[session_id] = tick_index + 1
        if self._positions[session_id] >= self.default_duration_ticks:
            self.store.set_session_status(session_id, "completed")
        return SimulationStep(
            session_id, scenario_key, tick_index, phase, progress, batch, analytics_result
        )

    def run_to_completion(self, session_id: str) -> list[SimulationStep]:
        steps: list[SimulationStep] = []
        while self.store.session_row(session_id)["status"] == "running":
            steps.append(self.advance(session_id))
        return steps

    @staticmethod
    def _phase(tick: int, duration: int) -> tuple[str, float]:
        baseline_ticks = min(5, max(1, duration // 3))
        recovery_ticks = max(2, duration // 4)
        onset_ticks = max(2, (duration - baseline_ticks - recovery_ticks) // 3)
        if tick < baseline_ticks:
            return "baseline", 0.0
        if tick < baseline_ticks + onset_ticks:
            return "onset", (tick - baseline_ticks + 1) / onset_ticks
        if tick < duration - recovery_ticks:
            return "degradation", 1.0
        remaining = max(0, duration - 1 - tick)
        return "recovery", remaining / recovery_ticks

    def _inject(
        self,
        baseline: TelemetryBatch,
        scenario: dict[str, object],
        facility_id: str,
        scenario_key: str,
        tick_index: int,
        timestamp: datetime,
    ) -> tuple[TelemetryBatch, float, str]:
        phase, intensity = self._phase(tick_index, self.default_duration_ticks)
        effects = dict(scenario["metric_effects"])
        metrics: list[TelemetryEvent] = []
        provenance = {
            "synthetic": True,
            "simulation_provenance": {
                "lab_version": self.version,
                "tick_index": tick_index,
                "phase": phase,
            },
        }
        for event in baseline.metrics:
            value = event.metric_value
            if event.facility_id == facility_id and event.metric_name in effects:
                effect = effects[event.metric_name]
                multiplier = 1.0 + (float(effect.get("peak_multiplier", 1.0)) - 1.0) * intensity
                addition = float(effect.get("peak_addition", 0.0)) * intensity
                oscillation = float(effect.get("oscillation", 0.0))
                value = value * multiplier + addition
                if oscillation:
                    value *= 1.0 + oscillation * math.sin(tick_index * math.pi / 2)
                definition = METRIC_DEFINITIONS[event.metric_name]
                value = min(definition.maximum, max(definition.minimum, value))
            metrics.append(TelemetryEvent.create(
                event_id=event.event_id,
                event_timestamp=event.event_timestamp,
                ingestion_timestamp=event.ingestion_timestamp,
                facility_id=event.facility_id,
                server_id=event.server_id,
                metric_name=event.metric_name,
                metric_value=value,
                unit=event.unit,
                source="simulation_lab",
                simulation_session_id=event.simulation_session_id,
                metadata={**event.metadata, **provenance},
            ))

        logs: list[LogEvent] = []
        alerts: list[AlertEvent] = []
        incidents: list[IncidentEvent] = []
        onset_tick = min(5, max(1, self.default_duration_ticks // 3))
        if tick_index in {
            onset_tick, self.default_duration_ticks // 2,
            self.default_duration_ticks - 2,
        }:
            is_recovery = phase == "recovery"
            suffix = f"{scenario_key}|{tick_index}|{facility_id}"
            logs.append(LogEvent(
                event_id=f"RTL-{uuid.uuid5(_LAB_NAMESPACE, 'log|'+suffix).hex.upper()}",
                event_timestamp=utc_iso(timestamp), ingestion_timestamp=utc_iso(timestamp),
                facility_id=facility_id, server_id=None,
                level=(
                    "info" if is_recovery else
                    {"low": "info", "medium": "warning", "high": "error", "critical": "critical"}[
                        str(scenario["severity"])
                    ]
                ),
                component="simulation_observer",
                event_code="RECOVERY_OBSERVED" if is_recovery else str(scenario["event_code"]),
                message=(
                    "Synthetic telemetry is returning toward its baseline."
                    if is_recovery else "Synthetic operational degradation observed."
                ),
                source="simulation_lab", quality_flag="valid",
                simulation_session_id=baseline.simulation_session_id or "",
                metadata=provenance,
            ))
            observed = next(
                (m.metric_value for m in metrics if m.facility_id == facility_id
                 and m.server_id is None and m.metric_name == scenario["alert_metric"]),
                None,
            )
            alert_metric = str(scenario["alert_metric"])
            if observed is None:
                observed = next(
                    m.metric_value for m in metrics
                    if m.facility_id == facility_id and m.metric_name == alert_metric
                )
            alerts.append(AlertEvent(
                alert_id=f"RTA-{uuid.uuid5(_LAB_NAMESPACE, 'alert|'+suffix).hex.upper()}",
                event_timestamp=utc_iso(timestamp), ingestion_timestamp=utc_iso(timestamp),
                facility_id=facility_id, server_id=None,
                metric_name=alert_metric, severity=str(scenario["severity"]),
                observed_value=observed, threshold_value=None,
                status="resolved" if is_recovery else "active", source="simulation_lab",
                quality_flag="valid", simulation_session_id=baseline.simulation_session_id or "",
                evidence={**provenance, "observable_only": True},
            ))
        if tick_index in {onset_tick + 2, self.default_duration_ticks - 1}:
            resolved = tick_index == self.default_duration_ticks - 1
            suffix = f"{scenario_key}|incident|{tick_index}|{facility_id}"
            incidents.append(IncidentEvent(
                incident_event_id=f"RTI-{uuid.uuid5(_LAB_NAMESPACE, suffix).hex.upper()}",
                incident_id=f"SIMINC-{uuid.uuid5(_LAB_NAMESPACE, scenario_key+'|'+facility_id).hex[:16].upper()}",
                event_timestamp=utc_iso(timestamp), ingestion_timestamp=utc_iso(timestamp),
                facility_id=facility_id, server_id=None,
                event_type="resolved" if resolved else "opened",
                severity=str(scenario["severity"]),
                status="resolved" if resolved else "active",
                summary=("Synthetic incident recovery observed." if resolved
                         else "Synthetic incident opened from observable evidence."),
                source="simulation_lab", simulation_session_id=baseline.simulation_session_id or "",
                evidence={**provenance, "observable_only": True},
            ))
        return TelemetryBatch(tuple(metrics), tuple(logs), tuple(alerts), tuple(incidents)), intensity, phase
