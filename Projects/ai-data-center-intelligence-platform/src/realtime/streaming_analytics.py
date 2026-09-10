"""Incremental state, rolling statistics and live-health orchestration."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.realtime.configuration import RealtimeConfig
from src.realtime.live_health import LiveHealthResult, LiveHealthService
from src.realtime.models import TelemetryBatch, utc_iso
from src.realtime.online_anomaly import OnlineAnomalyDetector, RealtimeAnomaly
from src.realtime.store import IngestionResult, RealtimeStore


@dataclass(frozen=True)
class StreamingAnalyticsResult:
    ingestion: IngestionResult
    anomalies: tuple[RealtimeAnomaly, ...]
    facility_health: tuple[LiveHealthResult, ...]
    rolling_groups: int
    state_version: int


@dataclass(frozen=True)
class LiveStatus:
    simulation_session_id: str
    event_version: int
    state_version: int
    state_is_current: bool
    metrics: tuple[dict[str, object], ...]
    rolling_statistics: tuple[dict[str, object], ...]
    active_anomalies: tuple[dict[str, object], ...]
    active_alerts: tuple[dict[str, object], ...]
    facility_health: tuple[dict[str, object], ...]


class StreamingAnalyticsService:
    """Convert stored telemetry into quickly queryable operational state."""

    def __init__(
        self,
        store: RealtimeStore,
        config: RealtimeConfig,
        live_health_weights_path: Path | str,
    ) -> None:
        self.store = store
        self.config = config
        self.anomaly_detector = OnlineAnomalyDetector(
            store,
            baseline_minutes=config.anomaly_baseline_minutes,
            minimum_samples=config.anomaly_minimum_samples,
            z_threshold=config.anomaly_z_threshold,
            active_minutes=config.anomaly_active_minutes,
        )
        self.health_service = LiveHealthService(store, live_health_weights_path)

    def process(self, batch: TelemetryBatch) -> StreamingAnalyticsResult:
        ingestion = self.store.ingest_batch(batch)
        self.store.upsert_metric_state(batch.metrics)
        anomalies = self.anomaly_detector.detect(batch.metrics)
        self.store.insert_anomalies([anomaly.as_row() for anomaly in anomalies])
        all_events = tuple(
            event
            for collection in (batch.metrics, batch.logs, batch.alerts, batch.incidents)
            for event in collection
        )
        latest_timestamp = max(event.event_timestamp for event in all_events)
        self.store.expire_anomalies(ingestion.simulation_session_id, latest_timestamp)
        rolling_rows = self._calculate_rolling_state(
            ingestion.simulation_session_id, latest_timestamp
        )
        self.store.replace_rolling_state(ingestion.simulation_session_id, rolling_rows)
        facility_ids = sorted({event.facility_id for event in all_events})
        health = tuple(
            result
            for facility_id in facility_ids
            if (result := self.health_service.calculate(
                ingestion.simulation_session_id, facility_id
            )) is not None
        )
        self.store.upsert_facility_health([result.as_row() for result in health])
        state_version = self.store.mark_state_current(ingestion.simulation_session_id)
        return StreamingAnalyticsResult(
            ingestion=ingestion,
            anomalies=tuple(anomalies),
            facility_health=health,
            rolling_groups=len(rolling_rows),
            state_version=state_version,
        )

    def _calculate_rolling_state(
        self, simulation_session_id: str, latest_timestamp: str
    ) -> list[tuple[object, ...]]:
        anchor = datetime.fromisoformat(latest_timestamp)
        since = utc_iso(anchor - timedelta(minutes=max(self.config.rolling_windows_minutes)))
        event_rows = self.store.recent_metric_rows(simulation_session_id, since)
        groups: dict[tuple[str, str, str | None, str, str], list[dict[str, object]]] = {}
        for row in event_rows:
            key = (
                str(row["facility_id"]),
                str(row["server_id"] or "__facility__"),
                str(row["server_id"]) if row["server_id"] is not None else None,
                str(row["metric_name"]),
                str(row["unit"]),
            )
            groups.setdefault(key, []).append(row)
        output: list[tuple[object, ...]] = []
        for (facility_id, scope_key, server_id, metric_name, unit), rows in groups.items():
            ordered = sorted(rows, key=lambda row: (str(row["event_timestamp"]), str(row["event_id"])))
            for window_minutes in self.config.rolling_windows_minutes:
                start = anchor - timedelta(minutes=window_minutes)
                selected = [
                    row for row in ordered
                    if datetime.fromisoformat(str(row["event_timestamp"])) >= start
                ]
                if not selected:
                    continue
                values = [float(row["metric_value"]) for row in selected]
                first_time = datetime.fromisoformat(str(selected[0]["event_timestamp"]))
                last_time = datetime.fromisoformat(str(selected[-1]["event_timestamp"]))
                elapsed_minutes = (last_time - first_time).total_seconds() / 60.0
                change_rate = (
                    (values[-1] - values[0]) / elapsed_minutes
                    if elapsed_minutes > 0 else 0.0
                )
                mean = statistics.fmean(values)
                output.append((
                    simulation_session_id,
                    facility_id,
                    scope_key,
                    server_id,
                    metric_name,
                    unit,
                    window_minutes,
                    utc_iso(start),
                    latest_timestamp,
                    len(values),
                    round(mean, 6),
                    round(min(values), 6),
                    round(max(values), 6),
                    round(statistics.pstdev(values), 6) if len(values) > 1 else 0.0,
                    round(change_rate, 6),
                    round(values[-1] - mean, 6),
                    round(values[-1], 6),
                    utc_iso(),
                ))
        return output

    def current_status(
        self, simulation_session_id: str, facility_id: str | None = None
    ) -> LiveStatus:
        event_version, state_version = self.store.session_versions(simulation_session_id)
        return LiveStatus(
            simulation_session_id=simulation_session_id,
            event_version=event_version,
            state_version=state_version,
            state_is_current=event_version == state_version,
            metrics=tuple(self.store.current_metric_rows(simulation_session_id, facility_id)),
            rolling_statistics=tuple(
                self.store.rolling_rows(simulation_session_id, facility_id=facility_id)
            ),
            active_anomalies=tuple(
                self.store.active_anomaly_rows(simulation_session_id, facility_id)
            ),
            active_alerts=tuple(
                self.store.active_alert_rows(simulation_session_id, facility_id)
            ),
            facility_health=tuple(
                self.store.facility_health_rows(simulation_session_id, facility_id)
            ),
        )
