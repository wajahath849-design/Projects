"""Deterministic live facility health derived from current operational state."""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.realtime.store import RealtimeStore


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, float(value)))


@dataclass(frozen=True)
class LiveHealthResult:
    simulation_session_id: str
    facility_id: str
    score_timestamp: str
    health_score: float
    energy_efficiency_score: float
    reliability_score: float
    network_health_score: float
    infrastructure_score: float
    alert_score: float
    anomaly_score: float
    active_alert_count: int
    active_anomaly_count: int
    data_completeness_pct: float
    drivers_json: str
    method_version: str

    def as_row(self) -> tuple[object, ...]:
        return tuple(self.__dict__.values())


class LiveHealthService:
    """Calculate explainable health components without LLM-generated values."""

    def __init__(self, store: RealtimeStore, weights_path: Path | str) -> None:
        self.store = store
        config = yaml.safe_load(Path(weights_path).read_text(encoding="utf-8"))
        self.method_version = str(config["version"])
        self.weights = {key: float(value) for key, value in config["weights"].items()}
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("Live health weights must sum to one")
        self.required_signals = config["required_signals"]

    def calculate(
        self, simulation_session_id: str, facility_id: str
    ) -> LiveHealthResult | None:
        rows = self.store.current_metric_rows(simulation_session_id, facility_id)
        if not rows:
            return None
        facility_metrics = {
            str(row["metric_name"]): float(row["metric_value"])
            for row in rows if row["server_id"] is None
        }
        server_metrics: dict[str, list[float]] = {}
        for row in rows:
            if row["server_id"] is not None:
                server_metrics.setdefault(str(row["metric_name"]), []).append(
                    float(row["metric_value"])
                )
        server_averages = {
            name: statistics.fmean(values) for name, values in server_metrics.items()
        }
        alerts = self.store.active_alert_rows(simulation_session_id, facility_id)
        anomalies = self.store.active_anomaly_rows(simulation_session_id, facility_id)

        pue = facility_metrics.get("pue")
        energy = 50.0 if pue is None else _clamp(100.0 - max(0.0, pue - 1.2) * 100.0)

        availability = facility_metrics.get("availability_pct")
        downtime = facility_metrics.get("downtime_minutes")
        incident = facility_metrics.get("incident_indicator")
        reliability_parts = []
        if availability is not None:
            reliability_parts.append(_clamp(availability))
        if downtime is not None:
            reliability_parts.append(_clamp(100.0 - downtime * 20.0))
        if incident is not None:
            reliability_parts.append(_clamp(100.0 - incident * 100.0))
        reliability = statistics.fmean(reliability_parts) if reliability_parts else 50.0

        network_parts = []
        latency = facility_metrics.get("latency_ms")
        packet_loss = facility_metrics.get("packet_loss_pct")
        network_availability = facility_metrics.get("network_availability_pct")
        if latency is not None:
            network_parts.append(_clamp(100.0 - max(0.0, latency - 5.0) * 2.5))
        if packet_loss is not None:
            network_parts.append(_clamp(100.0 - packet_loss * 25.0))
        if network_availability is not None:
            network_parts.append(_clamp(network_availability))
        network = statistics.fmean(network_parts) if network_parts else 50.0

        infrastructure_parts = []
        for metric in (
            "cpu_utilization_pct", "memory_utilization_pct", "disk_utilization_pct"
        ):
            value = server_averages.get(metric)
            if value is not None:
                infrastructure_parts.append(
                    _clamp(100.0 - max(0.0, value - 70.0) * (100.0 / 30.0))
                )
        temperature = server_averages.get("temperature_c")
        if temperature is not None:
            infrastructure_parts.append(
                _clamp(100.0 - max(0.0, temperature - 65.0) * (100.0 / 35.0))
            )
        infrastructure = (
            statistics.fmean(infrastructure_parts) if infrastructure_parts else 50.0
        )

        burden = {"low": 5.0, "medium": 10.0, "high": 20.0, "critical": 35.0}
        alert_score = _clamp(100.0 - sum(burden[str(row["severity"])] for row in alerts))
        anomaly_score = _clamp(
            100.0 - sum(burden[str(row["severity"])] for row in anomalies)
        )
        components = {
            "energy_efficiency": energy,
            "reliability": reliability,
            "network_health": network,
            "infrastructure": infrastructure,
            "alert_burden": alert_score,
            "anomaly_burden": anomaly_score,
        }
        health_score = sum(components[name] * self.weights[name] for name in components)

        available_signals = set(facility_metrics) | set(server_averages)
        required = {
            signal for signals in self.required_signals.values() for signal in signals
        }
        completeness = 100.0 * len(required & available_signals) / len(required)
        labels = {
            "energy_efficiency": "PUE and energy efficiency",
            "reliability": "Availability and incident pressure",
            "network_health": "Network performance",
            "infrastructure": "Server resource and temperature pressure",
            "alert_burden": "Active alert burden",
            "anomaly_burden": "Active anomaly burden",
        }
        drivers = []
        for name, score in components.items():
            if score < 85:
                severity = "high" if score < 40 else "medium" if score < 65 else "low"
                drivers.append({
                    "driver": labels[name],
                    "component": name,
                    "score": round(score, 2),
                    "severity": severity,
                    "calculation": "deterministic",
                })
        drivers.sort(key=lambda item: (item["score"], item["component"]))
        score_timestamp = max(str(row["event_timestamp"]) for row in rows)
        return LiveHealthResult(
            simulation_session_id=simulation_session_id,
            facility_id=facility_id,
            score_timestamp=score_timestamp,
            health_score=round(_clamp(health_score), 2),
            energy_efficiency_score=round(energy, 2),
            reliability_score=round(reliability, 2),
            network_health_score=round(network, 2),
            infrastructure_score=round(infrastructure, 2),
            alert_score=round(alert_score, 2),
            anomaly_score=round(anomaly_score, 2),
            active_alert_count=len(alerts),
            active_anomaly_count=len(anomalies),
            data_completeness_pct=round(completeness, 2),
            drivers_json=json.dumps(drivers, sort_keys=True),
            method_version=self.method_version,
        )
