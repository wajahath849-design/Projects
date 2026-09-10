"""Validated configuration for the local telemetry runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RealtimeConfig:
    version: str
    tick_interval_seconds: float
    server_sample_size_per_facility: int
    default_speed_multiplier: float
    random_seed: int
    retention_hours: int
    max_events_per_session: int
    queue_max_batches: int
    write_batch_size: int
    rolling_windows_minutes: tuple[int, ...]
    anomaly_baseline_minutes: int
    anomaly_minimum_samples: int
    anomaly_z_threshold: float
    anomaly_active_minutes: int
    maximum_lateness_seconds: int

    @classmethod
    def from_yaml(cls, path: Path | str) -> "RealtimeConfig":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        simulation = payload["simulation"]
        storage = payload["storage"]
        analytics = payload["analytics"]
        config = cls(
            version=str(payload["version"]),
            tick_interval_seconds=float(simulation["tick_interval_seconds"]),
            server_sample_size_per_facility=int(
                simulation["server_sample_size_per_facility"]
            ),
            default_speed_multiplier=float(simulation["default_speed_multiplier"]),
            random_seed=int(simulation["random_seed"]),
            retention_hours=int(storage["retention_hours"]),
            max_events_per_session=int(storage["max_events_per_session"]),
            queue_max_batches=int(storage["queue_max_batches"]),
            write_batch_size=int(storage["write_batch_size"]),
            rolling_windows_minutes=tuple(
                int(value) for value in analytics["rolling_windows_minutes"]
            ),
            anomaly_baseline_minutes=int(analytics["anomaly_baseline_minutes"]),
            anomaly_minimum_samples=int(analytics["anomaly_minimum_samples"]),
            anomaly_z_threshold=float(analytics["anomaly_z_threshold"]),
            anomaly_active_minutes=int(analytics["anomaly_active_minutes"]),
            maximum_lateness_seconds=int(analytics["maximum_lateness_seconds"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.tick_interval_seconds <= 0:
            raise ValueError("Telemetry tick interval must be positive")
        if self.server_sample_size_per_facility < 0:
            raise ValueError("Server sample size cannot be negative")
        if not 0 < self.default_speed_multiplier <= 100:
            raise ValueError("Simulation speed must be between 0 and 100")
        if not 1 <= self.retention_hours <= 720:
            raise ValueError("Retention must be between 1 and 720 hours")
        if not 1 <= self.max_events_per_session <= 5_000_000:
            raise ValueError("Maximum events per session is outside the safe range")
        if self.queue_max_batches < 1 or self.write_batch_size < 1:
            raise ValueError("Queue and batch limits must be positive")
        if tuple(sorted(set(self.rolling_windows_minutes))) != (1, 5, 15):
            raise ValueError("Supported rolling windows must be exactly 1, 5 and 15 minutes")
        if self.anomaly_minimum_samples < 3 or self.anomaly_z_threshold <= 0:
            raise ValueError("Anomaly baseline settings are invalid")
