"""Typed, validated event models for synthetic real-time operations data."""

from __future__ import annotations

import json
import math
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
QUALITY_FLAGS = frozenset({"valid", "suspect", "interpolated"})
SEVERITIES = frozenset({"low", "medium", "high", "critical"})


@dataclass(frozen=True)
class MetricDefinition:
    unit: str
    scope: str
    minimum: float
    maximum: float


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "cpu_utilization_pct": MetricDefinition("percent", "server", 0, 100),
    "memory_utilization_pct": MetricDefinition("percent", "server", 0, 100),
    "disk_utilization_pct": MetricDefinition("percent", "server", 0, 100),
    "network_utilization_pct": MetricDefinition("percent", "server", 0, 100),
    "temperature_c": MetricDefinition("celsius", "server", -20, 150),
    "server_status": MetricDefinition("state", "server", 0, 1),
    "power_draw_kw": MetricDefinition("kW", "facility", 0, 10_000_000),
    "it_load_kw": MetricDefinition("kW", "facility", 0, 10_000_000),
    "cooling_power_kw": MetricDefinition("kW", "facility", 0, 10_000_000),
    "pue": MetricDefinition("ratio", "facility", 1, 5),
    "energy_consumption_kwh": MetricDefinition("kWh", "facility", 0, 10_000_000),
    "bandwidth_utilization_pct": MetricDefinition("percent", "facility", 0, 100),
    "latency_ms": MetricDefinition("ms", "facility", 0, 1_000_000),
    "throughput_mbps": MetricDefinition("Mbps", "facility", 0, 100_000_000),
    "packet_loss_pct": MetricDefinition("percent", "facility", 0, 100),
    "network_availability_pct": MetricDefinition("percent", "facility", 0, 100),
    "availability_pct": MetricDefinition("percent", "facility", 0, 100),
    "downtime_minutes": MetricDefinition("minutes", "facility", 0, 1_440),
    "active_alert_count": MetricDefinition("count", "facility", 0, 1_000_000),
    "incident_indicator": MetricDefinition("state", "facility", 0, 1),
}


def utc_iso(value: datetime | str | None = None) -> str:
    """Return a canonical, timezone-aware UTC timestamp."""
    if value is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Event timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _validate_identifier(value: str, name: str) -> None:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {name}")


def safe_json(value: dict[str, Any], *, max_chars: int = 8_000) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    if len(payload) > max_chars:
        raise ValueError("Event metadata exceeds the safe size limit")
    return payload


@dataclass(frozen=True)
class TelemetryEvent:
    event_id: str
    event_timestamp: str
    ingestion_timestamp: str
    facility_id: str
    server_id: str | None
    metric_name: str
    metric_value: float
    unit: str
    source: str
    quality_flag: str
    simulation_session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        event_timestamp: datetime | str,
        facility_id: str,
        metric_name: str,
        metric_value: float,
        unit: str,
        source: str,
        simulation_session_id: str,
        server_id: str | None = None,
        quality_flag: str = "valid",
        metadata: dict[str, Any] | None = None,
        event_id: str | None = None,
        ingestion_timestamp: datetime | str | None = None,
    ) -> "TelemetryEvent":
        event = cls(
            event_id=event_id or f"RTM-{uuid.uuid4().hex.upper()}",
            event_timestamp=utc_iso(event_timestamp),
            ingestion_timestamp=utc_iso(ingestion_timestamp),
            facility_id=facility_id,
            server_id=server_id,
            metric_name=metric_name,
            metric_value=float(metric_value),
            unit=unit,
            source=source,
            quality_flag=quality_flag,
            simulation_session_id=simulation_session_id,
            metadata=dict(metadata or {}),
        )
        event.validate()
        return event

    def validate(self) -> None:
        for value, name in (
            (self.event_id, "event_id"),
            (self.facility_id, "facility_id"),
            (self.source, "source"),
            (self.simulation_session_id, "simulation_session_id"),
        ):
            _validate_identifier(value, name)
        if self.server_id:
            _validate_identifier(self.server_id, "server_id")
        definition = METRIC_DEFINITIONS.get(self.metric_name)
        if definition is None:
            raise ValueError(f"Unsupported real-time metric: {self.metric_name}")
        if self.unit != definition.unit:
            raise ValueError(
                f"Metric {self.metric_name} requires unit {definition.unit}, not {self.unit}"
            )
        if definition.scope == "server" and not self.server_id:
            raise ValueError(f"Metric {self.metric_name} requires server_id")
        if definition.scope == "facility" and self.server_id is not None:
            raise ValueError(f"Facility metric {self.metric_name} cannot carry server_id")
        if not math.isfinite(self.metric_value):
            raise ValueError("Metric value must be finite")
        if not definition.minimum <= self.metric_value <= definition.maximum:
            raise ValueError(f"Metric value is outside the allowed range for {self.metric_name}")
        if self.quality_flag not in QUALITY_FLAGS:
            raise ValueError("Unsupported quality flag")
        utc_iso(self.event_timestamp)
        utc_iso(self.ingestion_timestamp)
        safe_json(self.metadata)

    def as_row(self) -> tuple[object, ...]:
        return (
            self.event_id,
            self.event_timestamp,
            self.ingestion_timestamp,
            self.facility_id,
            self.server_id,
            self.metric_name,
            self.metric_value,
            self.unit,
            self.source,
            self.quality_flag,
            self.simulation_session_id,
            safe_json(self.metadata),
        )


@dataclass(frozen=True)
class LogEvent:
    event_id: str
    event_timestamp: str
    ingestion_timestamp: str
    facility_id: str
    server_id: str | None
    level: str
    component: str
    event_code: str
    message: str
    source: str
    quality_flag: str
    simulation_session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for value, name in (
            (self.event_id, "event_id"),
            (self.facility_id, "facility_id"),
            (self.event_code, "event_code"),
            (self.source, "source"),
            (self.simulation_session_id, "simulation_session_id"),
        ):
            _validate_identifier(value, name)
        if self.server_id:
            _validate_identifier(self.server_id, "server_id")
        if self.level not in {"info", "warning", "error", "critical"}:
            raise ValueError("Unsupported log level")
        if not self.component.strip() or len(self.component) > 100:
            raise ValueError("Invalid log component")
        if not self.message.strip() or len(self.message) > 4_000:
            raise ValueError("Invalid log message")
        if self.quality_flag not in QUALITY_FLAGS:
            raise ValueError("Unsupported quality flag")
        utc_iso(self.event_timestamp)
        utc_iso(self.ingestion_timestamp)
        safe_json(self.metadata)

    def as_row(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.event_id, self.event_timestamp, self.ingestion_timestamp,
            self.facility_id, self.server_id, self.level, self.component,
            self.event_code, self.message, self.source, self.quality_flag,
            self.simulation_session_id, safe_json(self.metadata),
        )


@dataclass(frozen=True)
class AlertEvent:
    alert_id: str
    event_timestamp: str
    ingestion_timestamp: str
    facility_id: str
    server_id: str | None
    metric_name: str
    severity: str
    observed_value: float | None
    threshold_value: float | None
    status: str
    source: str
    quality_flag: str
    simulation_session_id: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for value, name in (
            (self.alert_id, "alert_id"),
            (self.facility_id, "facility_id"),
            (self.source, "source"),
            (self.simulation_session_id, "simulation_session_id"),
        ):
            _validate_identifier(value, name)
        if self.server_id:
            _validate_identifier(self.server_id, "server_id")
        if self.metric_name not in METRIC_DEFINITIONS:
            raise ValueError("Alert metric is not governed")
        if self.severity not in SEVERITIES:
            raise ValueError("Unsupported alert severity")
        if self.status not in {"active", "acknowledged", "resolved"}:
            raise ValueError("Unsupported alert status")
        if self.quality_flag not in QUALITY_FLAGS:
            raise ValueError("Unsupported quality flag")
        for value in (self.observed_value, self.threshold_value):
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("Alert numeric values must be finite")
        utc_iso(self.event_timestamp)
        utc_iso(self.ingestion_timestamp)
        safe_json(self.evidence)

    def as_row(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.alert_id, self.event_timestamp, self.ingestion_timestamp,
            self.facility_id, self.server_id, self.metric_name, self.severity,
            self.observed_value, self.threshold_value, self.status, self.source,
            self.quality_flag, self.simulation_session_id, safe_json(self.evidence),
        )


@dataclass(frozen=True)
class IncidentEvent:
    incident_event_id: str
    incident_id: str
    event_timestamp: str
    ingestion_timestamp: str
    facility_id: str
    server_id: str | None
    event_type: str
    severity: str
    status: str
    summary: str
    source: str
    simulation_session_id: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for value, name in (
            (self.incident_event_id, "incident_event_id"),
            (self.incident_id, "incident_id"),
            (self.facility_id, "facility_id"),
            (self.source, "source"),
            (self.simulation_session_id, "simulation_session_id"),
        ):
            _validate_identifier(value, name)
        if self.server_id:
            _validate_identifier(self.server_id, "server_id")
        if self.event_type not in {"opened", "updated", "resolved"}:
            raise ValueError("Unsupported incident event type")
        if self.severity not in SEVERITIES:
            raise ValueError("Unsupported incident severity")
        if self.status not in {"active", "monitoring", "resolved"}:
            raise ValueError("Unsupported incident status")
        if not self.summary.strip() or len(self.summary) > 4_000:
            raise ValueError("Invalid incident summary")
        utc_iso(self.event_timestamp)
        utc_iso(self.ingestion_timestamp)
        safe_json(self.evidence)

    def as_row(self) -> tuple[object, ...]:
        self.validate()
        return (
            self.incident_event_id, self.incident_id, self.event_timestamp,
            self.ingestion_timestamp, self.facility_id, self.server_id,
            self.event_type, self.severity, self.status, self.summary, self.source,
            self.simulation_session_id, safe_json(self.evidence),
        )


@dataclass(frozen=True)
class TelemetryBatch:
    metrics: tuple[TelemetryEvent, ...] = ()
    logs: tuple[LogEvent, ...] = ()
    alerts: tuple[AlertEvent, ...] = ()
    incidents: tuple[IncidentEvent, ...] = ()

    @property
    def event_count(self) -> int:
        return len(self.metrics) + len(self.logs) + len(self.alerts) + len(self.incidents)

    @property
    def simulation_session_id(self) -> str | None:
        identifiers = {
            item.simulation_session_id
            for collection in (self.metrics, self.logs, self.alerts, self.incidents)
            for item in collection
        }
        if not identifiers:
            return None
        if len(identifiers) != 1:
            raise ValueError("A telemetry batch cannot mix simulation sessions")
        return next(iter(identifiers))
