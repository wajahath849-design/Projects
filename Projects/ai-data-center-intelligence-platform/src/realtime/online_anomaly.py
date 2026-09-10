"""Evidence-producing online anomaly detection for bounded telemetry windows."""

from __future__ import annotations

import json
import statistics
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.realtime.models import TelemetryEvent, utc_iso
from src.realtime.store import RealtimeStore


_ANOMALY_NAMESPACE = uuid.UUID("08953d65-96b1-4a82-8468-1b741d8aa67d")


@dataclass(frozen=True)
class RealtimeAnomaly:
    anomaly_id: str
    event_id: str
    anomaly_timestamp: str
    facility_id: str
    server_id: str | None
    metric_name: str
    observed_value: float
    expected_value: float
    lower_bound: float | None
    upper_bound: float | None
    deviation: float
    deviation_pct: float | None
    severity: str
    detection_method: str
    status: str
    active_until: str
    simulation_session_id: str
    evidence_json: str

    def as_row(self) -> tuple[object, ...]:
        return tuple(self.__dict__.values())


class OnlineAnomalyDetector:
    """Combine rolling z-scores with transparent operational thresholds."""

    HIGH_SIDE_THRESHOLDS: dict[str, tuple[float, float | None]] = {
        "cpu_utilization_pct": (95.0, 99.0),
        "memory_utilization_pct": (95.0, 99.0),
        "disk_utilization_pct": (95.0, 99.0),
        "temperature_c": (80.0, 90.0),
        "latency_ms": (50.0, 150.0),
        "packet_loss_pct": (2.0, 5.0),
        "pue": (1.8, 2.2),
    }
    LOW_SIDE_THRESHOLDS: dict[str, tuple[float, float | None]] = {
        "availability_pct": (99.0, 95.0),
        "network_availability_pct": (99.0, 95.0),
        "server_status": (0.5, 0.0),
    }

    def __init__(
        self,
        store: RealtimeStore,
        *,
        baseline_minutes: int = 15,
        minimum_samples: int = 5,
        z_threshold: float = 3.0,
        active_minutes: int = 15,
    ) -> None:
        self.store = store
        self.baseline_minutes = baseline_minutes
        self.minimum_samples = minimum_samples
        self.z_threshold = z_threshold
        self.active_minutes = active_minutes

    def detect(self, events: tuple[TelemetryEvent, ...]) -> list[RealtimeAnomaly]:
        anomalies: list[RealtimeAnomaly] = []
        for event in events:
            if event.quality_flag != "valid":
                continue
            timestamp = datetime.fromisoformat(event.event_timestamp)
            since = utc_iso(timestamp - timedelta(minutes=self.baseline_minutes))
            baseline = self.store.metric_history_before(event, since)
            mean = statistics.fmean(baseline) if baseline else None
            stddev = statistics.pstdev(baseline) if len(baseline) >= 2 else 0.0
            threshold_severity, threshold_reference = self._threshold_result(event)
            z_score = (
                abs(event.metric_value - mean) / stddev
                if mean is not None and len(baseline) >= self.minimum_samples and stddev > 1e-12
                else 0.0
            )
            statistical_severity = self._z_severity(z_score)
            severity = self._strongest(threshold_severity, statistical_severity)
            self.store.resolve_anomalies_for_event(event)
            if severity is None:
                continue
            expected = mean if mean is not None else float(threshold_reference)
            lower = mean - self.z_threshold * stddev if stddev > 0 and mean is not None else None
            upper = mean + self.z_threshold * stddev if stddev > 0 and mean is not None else None
            methods = []
            if threshold_severity:
                methods.append("governed_threshold")
            if statistical_severity:
                methods.append("rolling_zscore")
            deviation = event.metric_value - expected
            deviation_pct = None if abs(expected) < 1e-12 else 100.0 * deviation / abs(expected)
            anomaly_id = "RTA-" + uuid.uuid5(
                _ANOMALY_NAMESPACE, event.event_id
            ).hex.upper()
            anomalies.append(RealtimeAnomaly(
                anomaly_id=anomaly_id,
                event_id=event.event_id,
                anomaly_timestamp=event.event_timestamp,
                facility_id=event.facility_id,
                server_id=event.server_id,
                metric_name=event.metric_name,
                observed_value=event.metric_value,
                expected_value=round(expected, 6),
                lower_bound=round(lower, 6) if lower is not None else None,
                upper_bound=round(upper, 6) if upper is not None else None,
                deviation=round(deviation, 6),
                deviation_pct=round(deviation_pct, 6) if deviation_pct is not None else None,
                severity=severity,
                detection_method="+".join(methods),
                status="active",
                active_until=utc_iso(timestamp + timedelta(minutes=self.active_minutes)),
                simulation_session_id=event.simulation_session_id,
                evidence_json=json.dumps({
                    "event_id": event.event_id,
                    "baseline_sample_count": len(baseline),
                    "baseline_window_minutes": self.baseline_minutes,
                    "baseline_mean": round(mean, 6) if mean is not None else None,
                    "baseline_stddev": round(stddev, 6),
                    "z_score": round(z_score, 6),
                    "threshold_reference": threshold_reference,
                }, sort_keys=True),
            ))
        return anomalies

    @classmethod
    def _threshold_result(cls, event: TelemetryEvent) -> tuple[str | None, float | None]:
        if event.metric_name in cls.HIGH_SIDE_THRESHOLDS:
            high, critical = cls.HIGH_SIDE_THRESHOLDS[event.metric_name]
            if critical is not None and event.metric_value >= critical:
                return "critical", critical
            if event.metric_value >= high:
                return "high", high
        if event.metric_name in cls.LOW_SIDE_THRESHOLDS:
            high, critical = cls.LOW_SIDE_THRESHOLDS[event.metric_name]
            if critical is not None and event.metric_value <= critical:
                return "critical", critical
            if event.metric_value < high:
                return "high", high
        return None, None

    @staticmethod
    def _z_severity(z_score: float) -> str | None:
        if z_score >= 6:
            return "critical"
        if z_score >= 4:
            return "high"
        if z_score >= 3:
            return "medium"
        return None

    @staticmethod
    def _strongest(first: str | None, second: str | None) -> str | None:
        order = {None: 0, "medium": 1, "high": 2, "critical": 3}
        return first if order[first] >= order[second] else second
