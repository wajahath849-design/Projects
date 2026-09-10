"""Transparent weighted similarity search over historical incident evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.database import connect_read_only


@dataclass(frozen=True)
class IncidentProfile:
    incident_id: str
    facility_id: str
    facility_name: str
    start_time: str
    severity: str
    root_cause: str
    components: frozenset[str]
    log_codes: frozenset[str]
    alert_types: frozenset[str]
    anomaly_metrics: frozenset[str]
    resolution: str | None


@dataclass(frozen=True)
class SimilarIncident:
    incident: IncidentProfile
    similarity: float
    score_breakdown: dict[str, float]


class IncidentSimilarityEngine:
    WEIGHTS = {
        "components": 0.15,
        "log_codes": 0.25,
        "alert_types": 0.15,
        "anomaly_metrics": 0.15,
        "severity": 0.10,
        "root_cause": 0.15,
        "facility": 0.05,
    }

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    @staticmethod
    def _items(value: str | None) -> frozenset[str]:
        return frozenset(item for item in (value or "").split(",") if item)

    def profiles(self) -> list[IncidentProfile]:
        with connect_read_only(self.database_path) as connection:
            rows = connection.execute(
                """SELECT i.incident_id, i.facility_id, f.facility_name,
                    i.start_time, i.end_time, i.severity, i.root_cause,
                    (SELECT group_concat(DISTINCT l.component)
                     FROM system_logs AS l
                     WHERE l.facility_id=i.facility_id AND l.server_id=i.server_id
                       AND datetime(l.timestamp) BETWEEN datetime(i.start_time, '-15 minutes')
                                                     AND datetime(i.end_time)) AS components,
                    (SELECT group_concat(DISTINCT l.event_code)
                     FROM system_logs AS l
                     WHERE l.facility_id=i.facility_id AND l.server_id=i.server_id
                       AND datetime(l.timestamp) BETWEEN datetime(i.start_time, '-15 minutes')
                                                     AND datetime(i.end_time)) AS log_codes,
                    (SELECT group_concat(DISTINCT a.alert_type)
                     FROM alerts AS a
                     WHERE a.facility_id=i.facility_id AND a.server_id=i.server_id
                       AND datetime(a.timestamp) BETWEEN datetime(i.start_time, '-15 minutes')
                                                     AND datetime(i.end_time)) AS alert_types,
                    (SELECT group_concat(DISTINCT d.metric_name)
                     FROM detected_anomalies AS d
                     WHERE d.facility_id=i.facility_id
                       AND date(d.timestamp)=date(i.start_time)) AS anomaly_metrics,
                    (SELECT m.result FROM maintenance_actions AS m
                     WHERE m.incident_id=i.incident_id ORDER BY m.timestamp DESC LIMIT 1) AS resolution
                FROM uptime_incidents AS i
                JOIN facilities AS f ON f.facility_id=i.facility_id
                ORDER BY i.incident_id"""
            ).fetchall()
        return [IncidentProfile(
            incident_id=row["incident_id"],
            facility_id=row["facility_id"],
            facility_name=row["facility_name"],
            start_time=row["start_time"],
            severity=row["severity"],
            root_cause=row["root_cause"],
            components=self._items(row["components"]),
            log_codes=self._items(row["log_codes"]),
            alert_types=self._items(row["alert_types"]),
            anomaly_metrics=self._items(row["anomaly_metrics"]),
            resolution=row["resolution"],
        ) for row in rows]

    @staticmethod
    def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
        if not left and not right:
            return 0.0
        return len(left & right) / len(left | right)

    def compare(
        self, query: IncidentProfile, candidate: IncidentProfile
    ) -> SimilarIncident:
        breakdown = {
            "components": self._jaccard(query.components, candidate.components),
            "log_codes": self._jaccard(query.log_codes, candidate.log_codes),
            "alert_types": self._jaccard(query.alert_types, candidate.alert_types),
            "anomaly_metrics": self._jaccard(query.anomaly_metrics, candidate.anomaly_metrics),
            "severity": float(query.severity == candidate.severity),
            "root_cause": float(bool(query.root_cause) and query.root_cause == candidate.root_cause),
            "facility": float(bool(query.facility_id) and query.facility_id == candidate.facility_id),
        }
        similarity = sum(self.WEIGHTS[name] * value for name, value in breakdown.items())
        return SimilarIncident(candidate, round(similarity, 6), breakdown)

    def retrieve(self, incident_id: str, top_k: int = 5) -> list[SimilarIncident]:
        profiles = self.profiles()
        try:
            query = next(profile for profile in profiles if profile.incident_id == incident_id)
        except StopIteration as error:
            raise LookupError(f"Incident not found: {incident_id}") from error
        ranked = [self.compare(query, profile) for profile in profiles if profile.incident_id != incident_id]
        ranked.sort(
            key=lambda item: (
                -item.similarity,
                -int(item.incident.start_time.replace("-", "").replace(":", "").replace(" ", "")[:8]),
                item.incident.incident_id,
            )
        )
        return ranked[: max(1, min(int(top_k), 20))]

    def search_by_signals(
        self,
        components: Iterable[str] = (),
        log_codes: Iterable[str] = (),
        alert_types: Iterable[str] = (),
        anomaly_metrics: Iterable[str] = (),
        severity: str = "",
        facility_id: str = "",
        top_k: int = 5,
    ) -> list[SimilarIncident]:
        query = IncidentProfile(
            incident_id="NEW-SIGNALS",
            facility_id=facility_id,
            facility_name="",
            start_time="",
            severity=severity,
            root_cause="",
            components=frozenset(components),
            log_codes=frozenset(log_codes),
            alert_types=frozenset(alert_types),
            anomaly_metrics=frozenset(anomaly_metrics),
            resolution=None,
        )
        ranked = [self.compare(query, profile) for profile in self.profiles()]
        ranked.sort(key=lambda item: (-item.similarity, item.incident.incident_id))
        return ranked[: max(1, min(int(top_k), 20))]
