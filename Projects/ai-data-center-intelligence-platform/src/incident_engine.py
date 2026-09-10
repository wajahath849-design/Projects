"""Deterministic incident timelines and evidence-backed investigation summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from src.database import connect_read_only
from src.diagnostic_confidence import DiagnosticConfidenceEngine


@dataclass(frozen=True)
class TimelineEvent:
    event_id: str
    timestamp: str
    timestamp_precision: str
    source_type: str
    source_table: str
    source_record_id: str
    summary: str
    details: dict[str, Any]


@dataclass(frozen=True)
class IncidentTimeline:
    incident: dict[str, Any]
    window_start: str
    window_end: str
    events: list[TimelineEvent]


@dataclass(frozen=True)
class InvestigationResult:
    incident_id: str
    answer: str
    recorded_root_cause: str
    likely_area: str
    diagnostic_confidence: str
    confidence_score: int
    confidence_breakdown: dict[str, int]
    recommended_checks: list[str]
    evidence: dict[str, list[dict[str, Any]]]
    timeline: IncidentTimeline


class IncidentTimelineEngine:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def find_incidents(
        self,
        facility: str | None = None,
        date: str | None = None,
        server_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        clauses, parameters = [], []
        if facility:
            clauses.append("lower(f.facility_name) = lower(?)")
            parameters.append(facility)
        if date:
            clauses.append("date(i.start_time) = date(?)")
            parameters.append(date)
        if server_id:
            clauses.append("lower(i.server_id) = lower(?)")
            parameters.append(server_id)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"""SELECT i.*, f.facility_name, s.rack_id
        FROM uptime_incidents AS i
        JOIN facilities AS f ON f.facility_id = i.facility_id
        JOIN servers AS s ON s.server_id = i.server_id
        {where}
        ORDER BY i.start_time DESC, i.incident_id
        LIMIT ?"""
        parameters.append(max(1, min(int(limit), 100)))
        with connect_read_only(self.database_path) as connection:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

    def build(
        self,
        incident_id: str,
        before_minutes: int = 30,
        after_minutes: int = 15,
    ) -> IncidentTimeline:
        if not incident_id or len(incident_id) > 100:
            raise ValueError("A valid incident identifier is required")
        before_minutes = max(0, min(int(before_minutes), 1_440))
        after_minutes = max(0, min(int(after_minutes), 1_440))
        with connect_read_only(self.database_path) as connection:
            incident_row = connection.execute(
                """SELECT i.*, f.facility_name, s.rack_id
                FROM uptime_incidents AS i
                JOIN facilities AS f ON f.facility_id = i.facility_id
                JOIN servers AS s ON s.server_id = i.server_id
                WHERE i.incident_id = ?""",
                (incident_id,),
            ).fetchone()
            if incident_row is None:
                raise LookupError(f"Incident not found: {incident_id}")
            incident = dict(incident_row)
            start = datetime.fromisoformat(incident["start_time"])
            end = datetime.fromisoformat(incident["end_time"])
            window_start = start - timedelta(minutes=before_minutes)
            window_end = end + timedelta(minutes=after_minutes)
            events: list[TimelineEvent] = []

            date = incident["start_time"][:10]
            power = connection.execute(
                """SELECT metric_id, timestamp, pue, power_draw_kw, it_load_kw,
                    cooling_power_kw, cooling_cost
                FROM power_metrics WHERE facility_id = ? AND timestamp = ?""",
                (incident["facility_id"], date),
            ).fetchone()
            if power:
                details = dict(power)
                events.append(self._event(
                    f"{incident_id}:power_context", f"{date}T00:00:00", "day",
                    "metric", "power_metrics", power["metric_id"],
                    f"Daily power context: PUE {power['pue']:.3f}, power draw {power['power_draw_kw']:.2f} kW, cooling power {power['cooling_power_kw']:.2f} kW.",
                    details,
                ))
            network = connection.execute(
                """SELECT metric_id, timestamp, bandwidth_utilization_pct, latency_ms,
                    packet_loss_pct, throughput_mbps, network_availability_pct
                FROM network_metrics WHERE facility_id = ? AND timestamp = ?""",
                (incident["facility_id"], date),
            ).fetchone()
            if network:
                events.append(self._event(
                    f"{incident_id}:network_context", f"{date}T00:00:00", "day",
                    "metric", "network_metrics", network["metric_id"],
                    f"Daily network context: latency {network['latency_ms']:.3f} ms, packet loss {network['packet_loss_pct']:.3f}%, availability {network['network_availability_pct']:.4f}%.",
                    dict(network),
                ))
            server = connection.execute(
                """SELECT metric_id, timestamp, cpu_utilization_pct,
                    memory_utilization_pct, disk_utilization_pct, network_utilization_pct
                FROM server_metrics WHERE server_id = ? AND timestamp = ?""",
                (incident["server_id"], date),
            ).fetchone()
            if server:
                events.append(self._event(
                    f"{incident_id}:server_context", f"{date}T00:00:00", "day",
                    "metric", "server_metrics", server["metric_id"],
                    f"Daily server context: CPU {server['cpu_utilization_pct']:.2f}%, memory {server['memory_utilization_pct']:.2f}%, disk {server['disk_utilization_pct']:.2f}%.",
                    dict(server),
                ))

            for row in connection.execute(
                """SELECT * FROM system_logs
                WHERE facility_id = ? AND server_id = ?
                  AND datetime(timestamp) BETWEEN datetime(?) AND datetime(?)
                ORDER BY datetime(timestamp), log_id""",
                (
                    incident["facility_id"], incident["server_id"],
                    window_start.isoformat(timespec="minutes"),
                    window_end.isoformat(timespec="minutes"),
                ),
            ):
                events.append(self._event(
                    row["log_id"], row["timestamp"], "minute", "log", "system_logs",
                    row["log_id"], f"{row['log_level']} {row['event_code']}: {row['message']}",
                    dict(row),
                ))
            for row in connection.execute(
                """SELECT * FROM alerts
                WHERE facility_id = ? AND server_id = ?
                  AND datetime(timestamp) BETWEEN datetime(?) AND datetime(?)
                ORDER BY datetime(timestamp), alert_id""",
                (
                    incident["facility_id"], incident["server_id"],
                    window_start.isoformat(timespec="minutes"),
                    window_end.isoformat(timespec="minutes"),
                ),
            ):
                events.append(self._event(
                    row["alert_id"], row["timestamp"], "minute", "alert", "alerts",
                    row["alert_id"],
                    f"{row['severity'].upper()} alert {row['alert_type']}: {row['metric_name']} {row['observed_value']:.4f} vs threshold {row['threshold_value']:.4f}.",
                    dict(row),
                ))

            events.append(self._event(
                f"{incident_id}:start", incident["start_time"], "minute", "incident",
                "uptime_incidents", incident_id,
                f"Incident started; recorded severity {incident['severity']} and root-cause category {incident['root_cause']}.",
                incident,
            ))
            events.append(self._event(
                f"{incident_id}:end", incident["end_time"], "minute", "incident",
                "uptime_incidents", incident_id,
                f"Incident resolved after {incident['downtime_minutes']} downtime minutes.",
                incident,
            ))
            for row in connection.execute(
                "SELECT * FROM maintenance_actions WHERE incident_id = ? ORDER BY datetime(timestamp), action_id",
                (incident_id,),
            ):
                events.append(self._event(
                    row["action_id"], row["timestamp"], "minute", "maintenance",
                    "maintenance_actions", row["action_id"],
                    f"{row['performed_by_role']} recorded {row['action_type']}: {row['result']}",
                    dict(row),
                ))

        events.sort(key=lambda event: (event.timestamp, event.event_id))
        return IncidentTimeline(
            incident=incident,
            window_start=window_start.isoformat(timespec="minutes"),
            window_end=window_end.isoformat(timespec="minutes"),
            events=events,
        )

    @staticmethod
    def _event(
        event_id: str,
        timestamp: str,
        precision: str,
        source_type: str,
        source_table: str,
        source_record_id: str,
        summary: str,
        details: dict[str, Any],
    ) -> TimelineEvent:
        return TimelineEvent(
            event_id, timestamp, precision, source_type, source_table,
            source_record_id, summary, details,
        )


class RootCauseInvestigationEngine:
    def __init__(self, database_path: Path | str, project_root: Path | str) -> None:
        self.database_path = Path(database_path)
        self.project_root = Path(project_root)
        self.timeline_engine = IncidentTimelineEngine(database_path)
        self.incident_knowledge = yaml.safe_load(
            (self.project_root / "knowledge/incident_knowledge.yaml").read_text(encoding="utf-8")
        )["incidents"]
        self.runbooks = yaml.safe_load(
            (self.project_root / "knowledge/runbooks.yaml").read_text(encoding="utf-8")
        )["runbooks"]

    def investigate(self, incident_id: str) -> InvestigationResult:
        timeline = self.timeline_engine.build(incident_id)
        incident = timeline.incident
        knowledge_key = incident["root_cause"].replace(" ", "_")
        knowledge = self.incident_knowledge[knowledge_key]
        expected_codes = set(knowledge["common_log_codes"])
        logs = [asdict(event) for event in timeline.events if event.source_type == "log"]
        alerts = [asdict(event) for event in timeline.events if event.source_type == "alert"]
        metrics = [asdict(event) for event in timeline.events if event.source_type == "metric"]
        maintenance = [asdict(event) for event in timeline.events if event.source_type == "maintenance"]
        matching_logs = [
            event for event in logs if event["details"].get("event_code") in expected_codes
        ]
        with connect_read_only(self.database_path) as connection:
            anomalies = [dict(row) for row in connection.execute(
                """SELECT * FROM detected_anomalies
                WHERE facility_id = ? AND date(timestamp) = date(?)
                ORDER BY anomaly_score DESC, anomaly_id""",
                (incident["facility_id"], incident["start_time"][:10]),
            ).fetchall()]
            similar = [dict(row) for row in connection.execute(
                """SELECT i.incident_id, i.start_time, i.severity, i.root_cause,
                    f.facility_name, i.downtime_minutes, a.action_type,
                    a.description, a.result
                FROM uptime_incidents AS i
                JOIN facilities AS f ON f.facility_id = i.facility_id
                LEFT JOIN maintenance_actions AS a ON a.incident_id = i.incident_id
                WHERE i.root_cause = ? AND i.incident_id <> ?
                ORDER BY (i.facility_id = ?) DESC,
                    ABS(julianday(i.start_time) - julianday(?)), i.incident_id
                LIMIT 3""",
                (
                    incident["root_cause"], incident_id, incident["facility_id"],
                    incident["start_time"],
                ),
            ).fetchall()]

        runbook_name = knowledge["runbook"]
        runbook = self.runbooks[runbook_name]
        confidence_result = DiagnosticConfidenceEngine().calculate(
            correlated_metric_count=len(metrics) + len(anomalies),
            matching_log_code_count=len(matching_logs),
            alert_count=len(alerts),
            similar_incident_count=len(similar),
            confirmed_maintenance_count=len(maintenance),
            recorded_incident_category=True,
        )
        score = confidence_result.score
        confidence = confidence_result.level
        code_text = ", ".join(
            sorted({event["details"]["event_code"] for event in matching_logs})
        ) or "no matching expected codes"
        anomaly_text = (
            ", ".join(sorted({item["metric_name"] for item in anomalies}))
            if anomalies else "no same-day stored anomaly"
        )
        likely_area = ", ".join(knowledge["affected_components"][:2])
        answer = (
            f"The historical incident record classifies {incident_id} as {incident['root_cause']}. "
            f"The surrounding synthetic evidence is consistent with that category: matching log codes "
            f"{code_text}; {len(alerts)} threshold alert(s); and {anomaly_text}. "
            f"The likely area to inspect is {likely_area}. Diagnostic confidence is {confidence.lower()} "
            f"from a deterministic evidence score of {score}/{confidence_result.maximum}. {knowledge['limitation']} "
            "This is evidence-backed decision support, not proof of a more specific component cause."
        )
        evidence = {
            "metrics": metrics,
            "logs": logs,
            "alerts": alerts,
            "incidents": [incident],
            "maintenance": maintenance,
            "anomalies": anomalies,
            "similar_incidents": similar,
            "runbooks": [{
                "id": runbook_name,
                "title": runbook["title"],
                "source": "knowledge/runbooks.yaml",
                "safety": runbook["safety"],
            }],
        }
        return InvestigationResult(
            incident_id=incident_id,
            answer=answer,
            recorded_root_cause=incident["root_cause"],
            likely_area=likely_area,
            diagnostic_confidence=confidence,
            confidence_score=score,
            confidence_breakdown=confidence_result.breakdown,
            recommended_checks=list(knowledge["recommended_checks"]),
            evidence=evidence,
            timeline=timeline,
        )
