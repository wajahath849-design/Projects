"""Isolated SQLite storage for bounded real-time simulation evidence."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.database import connect_read_only
from src.realtime.models import TelemetryBatch, TelemetryEvent, utc_iso


@dataclass(frozen=True)
class IngestionResult:
    simulation_session_id: str
    metrics_inserted: int
    logs_inserted: int
    alerts_inserted: int
    incidents_inserted: int
    retained_metric_events: int
    event_version: int

    @property
    def total_inserted(self) -> int:
        return (
            self.metrics_inserted + self.logs_inserted
            + self.alerts_inserted + self.incidents_inserted
        )


class RealtimeStore:
    """Own the only trusted write path for the separate real-time database."""

    def __init__(
        self,
        realtime_database_path: Path | str,
        canonical_database_path: Path | str,
        schema_path: Path | str,
    ) -> None:
        self.database_path = Path(realtime_database_path)
        self.canonical_database_path = Path(canonical_database_path)
        self.schema_path = Path(schema_path)
        self._facilities, self._server_facilities = self._load_inventory()

    def _load_inventory(self) -> tuple[set[str], dict[str, str]]:
        with connect_read_only(self.canonical_database_path) as connection:
            facilities = {
                row["facility_id"]
                for row in connection.execute("SELECT facility_id FROM facilities")
            }
            servers = {
                row["server_id"]: row["facility_id"]
                for row in connection.execute("SELECT server_id, facility_id FROM servers")
            }
        return facilities, servers

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._write_connection() as connection:
            connection.executescript(schema)

    def _write_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def read_connection(self) -> sqlite3.Connection:
        return connect_read_only(self.database_path)

    def create_session(
        self,
        *,
        scenario_name: str = "normal_operations",
        speed_multiplier: float = 1.0,
        random_seed: int = 2026,
        retention_hours: int = 24,
        max_events: int = 250_000,
        metadata: dict[str, object] | None = None,
        simulation_session_id: str | None = None,
        started_at: datetime | str | None = None,
    ) -> str:
        if not scenario_name.strip() or len(scenario_name) > 100:
            raise ValueError("Invalid scenario name")
        if not 0 < speed_multiplier <= 100:
            raise ValueError("Simulation speed must be between 0 and 100")
        if not 1 <= retention_hours <= 720:
            raise ValueError("Retention must be between 1 and 720 hours")
        if not 1 <= max_events <= 5_000_000:
            raise ValueError("Maximum event count is outside the safe range")
        session_id = simulation_session_id or f"SIM-{uuid.uuid4().hex[:16].upper()}"
        timestamp = utc_iso(started_at)
        with self._write_connection() as connection:
            connection.execute(
                """INSERT INTO simulation_sessions (
                    simulation_session_id, scenario_name, status, started_at,
                    updated_at, speed_multiplier, random_seed, retention_hours,
                    max_events, metadata_json
                ) VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id, scenario_name, timestamp, timestamp,
                    float(speed_multiplier), int(random_seed), int(retention_hours),
                    int(max_events), json.dumps(metadata or {}, sort_keys=True),
                ),
            )
        return session_id

    def set_session_status(self, simulation_session_id: str, status: str) -> None:
        if status not in {"running", "paused", "completed", "stopped"}:
            raise ValueError("Unsupported simulation status")
        now = utc_iso()
        ended_at = now if status in {"completed", "stopped"} else None
        with self._write_connection() as connection:
            cursor = connection.execute(
                """UPDATE simulation_sessions
                SET status=?, updated_at=?, ended_at=?
                WHERE simulation_session_id=?""",
                (status, now, ended_at, simulation_session_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Simulation session does not exist")

    def set_session_speed(
        self, simulation_session_id: str, speed_multiplier: float
    ) -> None:
        """Update the playback rate without changing simulated timestamps."""
        if speed_multiplier not in {1.0, 2.0, 5.0, 10.0}:
            raise ValueError("Simulation speed must be one of 1x, 2x, 5x or 10x")
        with self._write_connection() as connection:
            cursor = connection.execute(
                """UPDATE simulation_sessions SET speed_multiplier=?, updated_at=?
                WHERE simulation_session_id=?""",
                (float(speed_multiplier), utc_iso(), simulation_session_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Simulation session does not exist")

    def reset_session(self, simulation_session_id: str) -> None:
        """Remove only one simulation's volatile evidence and return it to paused."""
        with self._write_connection() as connection:
            if connection.execute(
                "SELECT 1 FROM simulation_sessions WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone() is None:
                raise LookupError("Simulation session does not exist")
            # Parent event deletion cascades to state and anomaly rows. Other event
            # tables are independent children of the session and are cleared here.
            for table in (
                "realtime_metric_events",
                "realtime_log_events",
                "realtime_alert_events",
                "realtime_incident_events",
                "realtime_rolling_state",
                "realtime_facility_health",
            ):
                connection.execute(
                    f'DELETE FROM "{table}" WHERE simulation_session_id=?',
                    (simulation_session_id,),
                )
            connection.execute(
                """UPDATE simulation_sessions
                SET status='paused', ended_at=NULL, event_version=0,
                    state_version=0, updated_at=?
                WHERE simulation_session_id=?""",
                (utc_iso(), simulation_session_id),
            )

    def session_row(self, simulation_session_id: str) -> dict[str, object]:
        with self.read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM simulation_sessions WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone()
        if row is None:
            raise LookupError("Simulation session does not exist")
        return dict(row)

    def latest_session_id(self) -> str | None:
        with self.read_connection() as connection:
            row = connection.execute(
                """SELECT simulation_session_id FROM simulation_sessions
                ORDER BY updated_at DESC, simulation_session_id DESC LIMIT 1"""
            ).fetchone()
        return None if row is None else str(row[0])

    def _validate_scope(self, facility_id: str, server_id: str | None) -> None:
        if facility_id not in self._facilities:
            raise ValueError(f"Unknown canonical facility: {facility_id}")
        if server_id is not None:
            server_facility = self._server_facilities.get(server_id)
            if server_facility is None:
                raise ValueError(f"Unknown canonical server: {server_id}")
            if server_facility != facility_id:
                raise ValueError("Server does not belong to the supplied facility")

    def ingest_batch(self, batch: TelemetryBatch) -> IngestionResult:
        session_id = batch.simulation_session_id
        if session_id is None:
            raise ValueError("Cannot ingest an empty telemetry batch")
        for collection in (batch.metrics, batch.logs, batch.alerts, batch.incidents):
            for event in collection:
                event.validate()
                self._validate_scope(event.facility_id, event.server_id)
        reference_time = max(
            event.event_timestamp
            for collection in (batch.metrics, batch.logs, batch.alerts, batch.incidents)
            for event in collection
        )
        with self._write_connection() as connection:
            session = connection.execute(
                """SELECT status, retention_hours, max_events, event_version
                FROM simulation_sessions WHERE simulation_session_id=?""",
                (session_id,),
            ).fetchone()
            if session is None:
                raise LookupError("Simulation session does not exist")
            if session["status"] != "running":
                raise RuntimeError("Telemetry can only be ingested into a running session")
            if batch.metrics:
                connection.executemany(
                    "INSERT INTO realtime_metric_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [event.as_row() for event in batch.metrics],
                )
            if batch.logs:
                connection.executemany(
                    "INSERT INTO realtime_log_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [event.as_row() for event in batch.logs],
                )
            if batch.alerts:
                connection.executemany(
                    "INSERT INTO realtime_alert_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [event.as_row() for event in batch.alerts],
                )
            if batch.incidents:
                connection.executemany(
                    "INSERT INTO realtime_incident_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [event.as_row() for event in batch.incidents],
                )
            cutoff = utc_iso(
                datetime.fromisoformat(reference_time) - timedelta(hours=session["retention_hours"])
            )
            self._cleanup_with_connection(
                connection, session_id, cutoff, int(session["max_events"])
            )
            new_version = int(session["event_version"]) + 1
            connection.execute(
                """UPDATE simulation_sessions
                SET event_version=?, updated_at=? WHERE simulation_session_id=?""",
                (new_version, utc_iso(), session_id),
            )
            retained = connection.execute(
                "SELECT COUNT(*) FROM realtime_metric_events WHERE simulation_session_id=?",
                (session_id,),
            ).fetchone()[0]
        return IngestionResult(
            simulation_session_id=session_id,
            metrics_inserted=len(batch.metrics),
            logs_inserted=len(batch.logs),
            alerts_inserted=len(batch.alerts),
            incidents_inserted=len(batch.incidents),
            retained_metric_events=retained,
            event_version=new_version,
        )

    @staticmethod
    def _cleanup_with_connection(
        connection: sqlite3.Connection,
        session_id: str,
        cutoff: str,
        max_events: int,
    ) -> None:
        time_columns = {
            "realtime_metric_events": "event_timestamp",
            "realtime_log_events": "event_timestamp",
            "realtime_alert_events": "event_timestamp",
            "realtime_incident_events": "event_timestamp",
            "realtime_anomalies": "anomaly_timestamp",
        }
        id_columns = {
            "realtime_metric_events": "event_id",
            "realtime_log_events": "event_id",
            "realtime_alert_events": "alert_id",
            "realtime_incident_events": "incident_event_id",
            "realtime_anomalies": "anomaly_id",
        }
        for table, time_column in time_columns.items():
            connection.execute(
                f'DELETE FROM "{table}" WHERE simulation_session_id=? AND "{time_column}" < ?',
                (session_id, cutoff),
            )
            id_column = id_columns[table]
            connection.execute(
                f'''DELETE FROM "{table}" WHERE "{id_column}" IN (
                    SELECT "{id_column}" FROM "{table}"
                    WHERE simulation_session_id=?
                    ORDER BY "{time_column}" DESC, "{id_column}" DESC
                    LIMIT -1 OFFSET ?
                )''',
                (session_id, max_events),
            )
        connection.execute(
            """DELETE FROM realtime_rolling_state
            WHERE simulation_session_id=? AND window_end < ?""",
            (session_id, cutoff),
        )
        connection.execute(
            """DELETE FROM realtime_facility_health
            WHERE simulation_session_id=? AND score_timestamp < ?""",
            (session_id, cutoff),
        )

    def cleanup_session(
        self, simulation_session_id: str, reference_time: datetime | str | None = None
    ) -> int:
        with self._write_connection() as connection:
            session = connection.execute(
                "SELECT retention_hours, max_events FROM simulation_sessions WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone()
            if session is None:
                raise LookupError("Simulation session does not exist")
            reference = datetime.fromisoformat(utc_iso(reference_time))
            cutoff = utc_iso(reference - timedelta(hours=session["retention_hours"]))
            before = connection.execute(
                "SELECT COUNT(*) FROM realtime_metric_events WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone()[0]
            self._cleanup_with_connection(
                connection, simulation_session_id, cutoff, int(session["max_events"])
            )
            after = connection.execute(
                "SELECT COUNT(*) FROM realtime_metric_events WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone()[0]
            return before - after

    def session_versions(self, simulation_session_id: str) -> tuple[int, int]:
        with self.read_connection() as connection:
            row = connection.execute(
                """SELECT event_version, state_version FROM simulation_sessions
                WHERE simulation_session_id=?""",
                (simulation_session_id,),
            ).fetchone()
        if row is None:
            raise LookupError("Simulation session does not exist")
        return int(row["event_version"]), int(row["state_version"])

    def upsert_metric_state(self, events: tuple[TelemetryEvent, ...]) -> None:
        if not events:
            return
        rows = [
            (
                event.simulation_session_id,
                event.facility_id,
                event.server_id or "__facility__",
                event.server_id,
                event.metric_name,
                event.metric_value,
                event.unit,
                event.event_id,
                event.event_timestamp,
                event.quality_flag,
            )
            for event in events
        ]
        with self._write_connection() as connection:
            connection.executemany(
                """INSERT INTO realtime_metric_state VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(simulation_session_id, facility_id, scope_key, metric_name)
                DO UPDATE SET
                    server_id=excluded.server_id,
                    metric_value=excluded.metric_value,
                    unit=excluded.unit,
                    event_id=excluded.event_id,
                    event_timestamp=excluded.event_timestamp,
                    quality_flag=excluded.quality_flag
                WHERE excluded.event_timestamp >= realtime_metric_state.event_timestamp""",
                rows,
            )

    def replace_rolling_state(
        self, simulation_session_id: str, rows: list[tuple[object, ...]]
    ) -> None:
        with self._write_connection() as connection:
            connection.execute(
                "DELETE FROM realtime_rolling_state WHERE simulation_session_id=?",
                (simulation_session_id,),
            )
            if rows:
                connection.executemany(
                    "INSERT INTO realtime_rolling_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )

    def resolve_anomalies_for_event(self, event: TelemetryEvent) -> None:
        with self._write_connection() as connection:
            connection.execute(
                """UPDATE realtime_anomalies SET status='resolved'
                WHERE simulation_session_id=? AND facility_id=?
                  AND (server_id=? OR (server_id IS NULL AND ? IS NULL))
                  AND metric_name=? AND status='active' AND anomaly_timestamp < ?""",
                (
                    event.simulation_session_id, event.facility_id,
                    event.server_id, event.server_id, event.metric_name,
                    event.event_timestamp,
                ),
            )

    def insert_anomalies(self, rows: list[tuple[object, ...]]) -> None:
        if not rows:
            return
        with self._write_connection() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO realtime_anomalies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def expire_anomalies(self, simulation_session_id: str, as_of: str) -> None:
        with self._write_connection() as connection:
            connection.execute(
                """UPDATE realtime_anomalies SET status='resolved'
                WHERE simulation_session_id=? AND status='active' AND active_until < ?""",
                (simulation_session_id, as_of),
            )

    def upsert_facility_health(self, rows: list[tuple[object, ...]]) -> None:
        if not rows:
            return
        with self._write_connection() as connection:
            connection.executemany(
                """INSERT INTO realtime_facility_health VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(simulation_session_id, facility_id) DO UPDATE SET
                    score_timestamp=excluded.score_timestamp,
                    health_score=excluded.health_score,
                    energy_efficiency_score=excluded.energy_efficiency_score,
                    reliability_score=excluded.reliability_score,
                    network_health_score=excluded.network_health_score,
                    infrastructure_score=excluded.infrastructure_score,
                    alert_score=excluded.alert_score,
                    anomaly_score=excluded.anomaly_score,
                    active_alert_count=excluded.active_alert_count,
                    active_anomaly_count=excluded.active_anomaly_count,
                    data_completeness_pct=excluded.data_completeness_pct,
                    drivers_json=excluded.drivers_json,
                    method_version=excluded.method_version""",
                rows,
            )

    def mark_state_current(self, simulation_session_id: str) -> int:
        with self._write_connection() as connection:
            row = connection.execute(
                "SELECT event_version FROM simulation_sessions WHERE simulation_session_id=?",
                (simulation_session_id,),
            ).fetchone()
            if row is None:
                raise LookupError("Simulation session does not exist")
            version = int(row["event_version"])
            connection.execute(
                """UPDATE simulation_sessions SET state_version=?, updated_at=?
                WHERE simulation_session_id=?""",
                (version, utc_iso(), simulation_session_id),
            )
        return version

    def current_metric_rows(
        self, simulation_session_id: str, facility_id: str | None = None
    ) -> list[dict[str, object]]:
        sql = "SELECT * FROM realtime_metric_state WHERE simulation_session_id=?"
        params: list[object] = [simulation_session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY facility_id, scope_key, metric_name"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def rolling_rows(
        self,
        simulation_session_id: str,
        *,
        facility_id: str | None = None,
        metric_name: str | None = None,
    ) -> list[dict[str, object]]:
        sql = "SELECT * FROM realtime_rolling_state WHERE simulation_session_id=?"
        params: list[object] = [simulation_session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        if metric_name:
            sql += " AND metric_name=?"
            params.append(metric_name)
        sql += " ORDER BY facility_id, scope_key, metric_name, window_minutes"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def active_anomaly_rows(
        self, simulation_session_id: str, facility_id: str | None = None
    ) -> list[dict[str, object]]:
        sql = """SELECT * FROM realtime_anomalies
        WHERE simulation_session_id=? AND status='active'"""
        params: list[object] = [simulation_session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY anomaly_timestamp, anomaly_id"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def active_alert_rows(
        self, simulation_session_id: str, facility_id: str | None = None
    ) -> list[dict[str, object]]:
        sql = """SELECT * FROM realtime_alert_events
        WHERE simulation_session_id=? AND status IN ('active', 'acknowledged')"""
        params: list[object] = [simulation_session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY event_timestamp, alert_id"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def facility_health_rows(
        self, simulation_session_id: str, facility_id: str | None = None
    ) -> list[dict[str, object]]:
        sql = "SELECT * FROM realtime_facility_health WHERE simulation_session_id=?"
        params: list[object] = [simulation_session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY facility_id"
        with self.read_connection() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def recent_metric_rows(
        self, simulation_session_id: str, since: str
    ) -> list[dict[str, object]]:
        with self.read_connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """SELECT * FROM realtime_metric_events
                    WHERE simulation_session_id=? AND event_timestamp>=?
                    ORDER BY event_timestamp, event_id""",
                    (simulation_session_id, since),
                ).fetchall()
            ]

    def metric_history_before(
        self,
        event: TelemetryEvent,
        since: str,
        limit: int = 2_000,
    ) -> list[float]:
        with self.read_connection() as connection:
            rows = connection.execute(
                """SELECT metric_value FROM realtime_metric_events
                WHERE simulation_session_id=? AND facility_id=?
                  AND (server_id=? OR (server_id IS NULL AND ? IS NULL))
                  AND metric_name=? AND event_timestamp>=? AND event_timestamp<?
                  AND quality_flag='valid'
                ORDER BY event_timestamp DESC, event_id DESC LIMIT ?""",
                (
                    event.simulation_session_id, event.facility_id,
                    event.server_id, event.server_id, event.metric_name,
                    since, event.event_timestamp, int(limit),
                ),
            ).fetchall()
        return [float(row["metric_value"]) for row in reversed(rows)]
