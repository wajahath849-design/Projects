"""Selective specialist investigation over observable operational evidence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.database import connect_read_only
from src.investigation.evidence import EvidenceRecord, deduplicate_evidence
from src.realtime.store import RealtimeStore


@dataclass(frozen=True)
class SpecialistFinding:
    agent: str
    summary: str
    evidence_ids: tuple[str, ...]
    status: str = "ok"


@dataclass(frozen=True)
class InvestigationReport:
    simulation_session_id: str
    route: str
    invoked_agents: tuple[str, ...]
    incident_summary: str
    first_abnormal_signal: dict[str, object] | None
    evidence_timeline: tuple[EvidenceRecord, ...]
    likely_contributor: str
    alternative_explanations: tuple[str, ...]
    similar_incidents: tuple[dict[str, object], ...]
    maintenance_or_runbook_guidance: tuple[str, ...]
    confidence_label: str
    confidence_basis: str
    recommended_inspections: tuple[str, ...]
    uncertainty: str
    findings: tuple[SpecialistFinding, ...]
    claim_evidence_ids: dict[str, tuple[str, ...]]
    verified: bool
    partial_failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "simulation_session_id": self.simulation_session_id,
            "route": self.route,
            "invoked_agents": list(self.invoked_agents),
            "incident_summary": self.incident_summary,
            "first_abnormal_signal": self.first_abnormal_signal,
            "evidence_timeline": [row.to_dict() for row in self.evidence_timeline],
            "likely_contributor": self.likely_contributor,
            "alternative_explanations": list(self.alternative_explanations),
            "similar_incidents": list(self.similar_incidents),
            "maintenance_or_runbook_guidance": list(self.maintenance_or_runbook_guidance),
            "confidence_label": self.confidence_label,
            "confidence_basis": self.confidence_basis,
            "recommended_inspections": list(self.recommended_inspections),
            "uncertainty": self.uncertainty,
            "findings": [finding.__dict__ for finding in self.findings],
            "claim_evidence_ids": self.claim_evidence_ids,
            "verified": self.verified,
            "partial_failures": list(self.partial_failures),
        }


class EvidenceVerifier:
    """Reject major claims that do not reference retrieved evidence."""

    REQUIRED_CLAIMS = frozenset({"summary", "first_signal", "likely_contributor"})

    def verify(
        self,
        evidence: tuple[EvidenceRecord, ...],
        claim_evidence_ids: dict[str, tuple[str, ...]],
    ) -> bool:
        existing = {item.evidence_id for item in evidence}
        for claim in self.REQUIRED_CLAIMS:
            references = claim_evidence_ids.get(claim, ())
            if not references or not set(references) <= existing:
                return False
        return True


class MultiAgentInvestigationService:
    """Invoke only the analysts needed by incident complexity."""

    DOMAIN_METRICS = {
        "cooling": {
            "pue", "cooling_power_kw", "temperature_c",
            "COOLING_PERFORMANCE_DEGRADED",
        },
        "network": {
            "latency_ms", "packet_loss_pct", "throughput_mbps",
            "bandwidth_utilization_pct", "NETWORK_CONGESTION",
        },
        "compute": {
            "cpu_utilization_pct", "memory_utilization_pct",
            "SERVER_RESOURCE_SATURATION",
        },
        "storage": {"disk_utilization_pct", "STORAGE_CAPACITY_PRESSURE"},
        "reliability": {
            "availability_pct", "downtime_minutes", "incident_indicator",
            "MULTI_DOMAIN_DEGRADATION",
        },
        "power": {"power_draw_kw", "it_load_kw", "POWER_FEED_UNSTABLE"},
    }

    def __init__(
        self,
        store: RealtimeStore,
        historical_database_path: Path | str,
        synthesizer: Callable[[dict[str, object]], str] | None = None,
    ) -> None:
        self.store = store
        self.historical_database_path = Path(historical_database_path)
        self.synthesizer = synthesizer
        self.verifier = EvidenceVerifier()

    def route(self, session_id: str, facility_id: str | None = None) -> str:
        with self.store.read_connection() as connection:
            params: list[object] = [session_id]
            facility_sql = ""
            if facility_id:
                facility_sql = " AND facility_id=?"
                params.append(facility_id)
            metrics = {
                row[0] for row in connection.execute(
                    "SELECT DISTINCT metric_name FROM realtime_anomalies "
                    "WHERE simulation_session_id=? AND status='active'" + facility_sql,
                    params,
                )
            }
            critical = connection.execute(
                "SELECT COUNT(*) FROM realtime_incident_events "
                "WHERE simulation_session_id=? AND severity='critical'" + facility_sql,
                params,
            ).fetchone()[0]
            high_alerts = connection.execute(
                "SELECT COUNT(*) FROM realtime_alert_events "
                "WHERE simulation_session_id=? AND severity IN ('high','critical')"
                + facility_sql,
                params,
            ).fetchone()[0]
        domains = sum(bool(values & metrics) for values in self.DOMAIN_METRICS.values())
        return (
            "multi_agent"
            if critical or high_alerts or domains >= 2 or len(metrics) >= 3
            else "deterministic_simple"
        )

    def investigate(
        self, session_id: str, facility_id: str | None = None
    ) -> InvestigationReport:
        route = self.route(session_id, facility_id)
        evidence: list[EvidenceRecord] = []
        findings: list[SpecialistFinding] = []
        invoked = ["metric_analyst", "anomaly_analyst"]
        try:
            metric_evidence, metric_finding = self._metric_analyst(session_id, facility_id)
        except Exception as error:  # specialist isolation is deliberate
            metric_evidence = []
            metric_finding = self._failure_finding("metric_analyst", error)
        evidence.extend(metric_evidence)
        findings.append(metric_finding)
        try:
            anomaly_evidence, anomaly_finding = self._anomaly_analyst(session_id, facility_id)
        except Exception as error:  # specialist isolation is deliberate
            anomaly_evidence = []
            anomaly_finding = self._failure_finding("anomaly_analyst", error)
        evidence.extend(anomaly_evidence)
        findings.append(anomaly_finding)
        similar: tuple[dict[str, object], ...] = ()
        guidance: tuple[str, ...] = ()
        if route == "multi_agent":
            invoked.append("log_alert_analyst")
            try:
                log_evidence, log_finding = self._log_alert_analyst(session_id, facility_id)
            except Exception as error:  # specialist isolation is deliberate
                log_evidence = []
                log_finding = self._failure_finding("log_alert_analyst", error)
            evidence.extend(log_evidence)
            findings.append(log_finding)
            invoked.append("historical_analyst")
            try:
                similar, historical_evidence, historical_finding = self._historical_analyst(
                    session_id, facility_id, evidence
                )
            except Exception as error:  # specialist isolation is deliberate
                similar, historical_evidence = (), []
                historical_finding = self._failure_finding("historical_analyst", error)
            evidence.extend(historical_evidence)
            findings.append(historical_finding)
            invoked.append("maintenance_runbook_analyst")
            try:
                guidance, maintenance_evidence, maintenance_finding = self._maintenance_analyst(similar)
            except Exception as error:  # specialist isolation is deliberate
                guidance, maintenance_evidence = (), []
                maintenance_finding = self._failure_finding(
                    "maintenance_runbook_analyst", error
                )
            evidence.extend(maintenance_evidence)
            findings.append(maintenance_finding)
        timeline = deduplicate_evidence(evidence)
        contributor, alternatives, contributor_ids = self._hypothesis(timeline)
        first_record = self._first_abnormal_signal(timeline, contributor)
        first = first_record.to_dict() if first_record else None
        summary_ids = tuple(item.evidence_id for item in timeline[: min(5, len(timeline))])
        first_ids = (first_record.evidence_id,) if first_record else ()
        claims = {
            "summary": summary_ids,
            "first_signal": first_ids,
            "likely_contributor": contributor_ids,
        }
        verified = self.verifier.verify(timeline, claims)
        confidence = self._confidence(timeline, route, verified)
        summary = (
            f"{len(timeline)} observable evidence records were reviewed across "
            f"{len(invoked)} analysts. {contributor}"
        )
        if self.synthesizer is not None:
            # The optional local model sees bounded structured evidence only. Its
            # wording cannot change evidence references or the verified label.
            try:
                proposed = self.synthesizer({
                    "summary": summary,
                    "confidence": confidence,
                    "evidence": [item.to_dict() for item in timeline[:50]],
                })
                cited = {
                    item.evidence_id for item in timeline if item.evidence_id in proposed
                } if isinstance(proposed, str) else set()
                if proposed and len(proposed) <= 2_000 and cited:
                    summary = proposed
                elif proposed:
                    findings.append(SpecialistFinding(
                        "root_cause_synthesizer",
                        "Local-model wording was rejected because it did not cite retrieved evidence.",
                        (),
                        "rejected",
                    ))
            except Exception as error:
                findings.append(self._failure_finding("root_cause_synthesizer", error))
        partial_failures = tuple(
            finding.agent for finding in findings if finding.status == "failed"
        )
        if partial_failures and confidence == "LIKELY":
            confidence = "POSSIBLE"
        if not verified:
            confidence = "INSUFFICIENT_EVIDENCE"
            contributor = "No contributor can be supported from the retrieved evidence."
        return InvestigationReport(
            simulation_session_id=session_id,
            route=route,
            invoked_agents=tuple(invoked),
            incident_summary=summary,
            first_abnormal_signal=first,
            evidence_timeline=timeline,
            likely_contributor=contributor,
            alternative_explanations=alternatives,
            similar_incidents=similar,
            maintenance_or_runbook_guidance=guidance,
            confidence_label=confidence,
            confidence_basis=(
                "Qualitative label based on independent observable source types, "
                "cross-domain agreement, and verified evidence references; not a probability."
            ),
            recommended_inspections=self._inspections(timeline),
            uncertainty=(
                "The simulation's hidden evaluation truth was not queried. Findings describe "
                "observable associations and require operator confirmation."
            ),
            findings=tuple(findings),
            claim_evidence_ids=claims,
            verified=verified,
            partial_failures=partial_failures,
        )

    @staticmethod
    def _failure_finding(agent: str, error: Exception) -> SpecialistFinding:
        """Return a safe failure marker without leaking data or chain-of-thought."""
        return SpecialistFinding(
            agent=agent,
            summary=(
                f"{agent.replace('_', ' ').title()} was unavailable; the investigation "
                f"continued with partial evidence ({type(error).__name__})."
            ),
            evidence_ids=(),
            status="failed",
        )

    def _metric_analyst(
        self, session_id: str, facility_id: str | None
    ) -> tuple[list[EvidenceRecord], SpecialistFinding]:
        sql = """SELECT event_id, event_timestamp, facility_id, server_id,
            metric_name, metric_value, unit FROM realtime_metric_events
            WHERE simulation_session_id=?"""
        params: list[object] = [session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY event_timestamp DESC, event_id DESC LIMIT 500"
        with self.store.read_connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        grouped: dict[tuple[str, str | None, str], list[object]] = {}
        for row in reversed(rows):
            grouped.setdefault((row["facility_id"], row["server_id"], row["metric_name"]), []).append(row)
        records: list[EvidenceRecord] = []
        changes: list[tuple[float, object]] = []
        for values in grouped.values():
            if len(values) < 2:
                continue
            first = values[0]
            denominator = max(abs(float(first["metric_value"])), 1e-9)
            peak = max(
                values[1:],
                key=lambda row: abs(float(row["metric_value"]) - float(first["metric_value"])),
            )
            changes.append((
                abs(float(peak["metric_value"]) - float(first["metric_value"])) / denominator,
                peak,
            ))
        for change, row in sorted(changes, key=lambda item: -item[0])[:8]:
            records.append(EvidenceRecord(
                str(row["event_id"]), "metric_change", "realtime_metric_events",
                str(row["event_timestamp"]), str(row["facility_id"]), row["server_id"],
                str(row["metric_name"]),
                {"value": float(row["metric_value"]), "unit": row["unit"], "absolute_change_pct": round(change * 100, 3)},
                None, "Largest recent baseline-to-current changes", "metric_analyst",
            ))
        ids = tuple(row.evidence_id for row in records)
        summary = f"Structured {len(records)} largest baseline-to-current metric changes."
        return records, SpecialistFinding("metric_analyst", summary, ids)

    def _anomaly_analyst(
        self, session_id: str, facility_id: str | None
    ) -> tuple[list[EvidenceRecord], SpecialistFinding]:
        sql = "SELECT * FROM realtime_anomalies WHERE simulation_session_id=?"
        params: list[object] = [session_id]
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        sql += " ORDER BY anomaly_timestamp, anomaly_id LIMIT 100"
        with self.store.read_connection() as connection:
            rows = connection.execute(sql, params).fetchall()
        records = [EvidenceRecord(
            str(row["anomaly_id"]), "anomaly", "realtime_anomalies",
            str(row["anomaly_timestamp"]), str(row["facility_id"]), row["server_id"],
            str(row["metric_name"]),
            {"observed": row["observed_value"], "expected": row["expected_value"], "deviation_pct": row["deviation_pct"]},
            str(row["severity"]), "Online anomaly ordered by first detection", "anomaly_analyst",
        ) for row in rows]
        ids = tuple(row.evidence_id for row in records)
        return records, SpecialistFinding(
            "anomaly_analyst", f"Ordered {len(records)} online anomalies by first detection.", ids
        )

    def _log_alert_analyst(
        self, session_id: str, facility_id: str | None
    ) -> tuple[list[EvidenceRecord], SpecialistFinding]:
        records: list[EvidenceRecord] = []
        with self.store.read_connection() as connection:
            params: list[object] = [session_id]
            suffix = ""
            if facility_id:
                suffix = " AND facility_id=?"
                params.append(facility_id)
            logs = connection.execute(
                "SELECT * FROM realtime_log_events WHERE simulation_session_id=?" + suffix +
                " ORDER BY event_timestamp, event_id LIMIT 50", params,
            ).fetchall()
            alerts = connection.execute(
                "SELECT * FROM realtime_alert_events WHERE simulation_session_id=?" + suffix +
                " ORDER BY event_timestamp, alert_id LIMIT 50", params,
            ).fetchall()
        for row in logs:
            records.append(EvidenceRecord(
                str(row["event_id"]), "log", "realtime_log_events",
                str(row["event_timestamp"]), str(row["facility_id"]), row["server_id"],
                str(row["event_code"]),
                {"component": row["component"], "level": row["level"], "message_is_untrusted_data": True},
                str(row["level"]), "Log content retained as data and never treated as instructions", "log_alert_analyst",
            ))
        for row in alerts:
            records.append(EvidenceRecord(
                str(row["alert_id"]), "alert", "realtime_alert_events",
                str(row["event_timestamp"]), str(row["facility_id"]), row["server_id"],
                str(row["metric_name"]),
                {"observed": row["observed_value"], "threshold": row["threshold_value"], "status": row["status"]},
                str(row["severity"]), "Alert corroborates an observed metric condition", "log_alert_analyst",
            ))
        ids = tuple(item.evidence_id for item in records)
        return records, SpecialistFinding(
            "log_alert_analyst", f"Reviewed {len(logs)} logs and {len(alerts)} alerts as untrusted data.", ids
        )

    def _historical_analyst(
        self,
        session_id: str,
        facility_id: str | None,
        current: list[EvidenceRecord],
    ) -> tuple[tuple[dict[str, object], ...], list[EvidenceRecord], SpecialistFinding]:
        severities = [item.severity for item in current if item.severity]
        severity = Counter(severities).most_common(1)[0][0] if severities else None
        sql = """SELECT incident_id, facility_id, server_id, start_time,
            severity, root_cause, downtime_minutes, status
            FROM uptime_incidents WHERE 1=1"""
        params: list[object] = []
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        if severity in {"low", "medium", "high", "critical"}:
            sql += " AND severity=?"
            params.append(severity)
        sql += " ORDER BY start_time DESC, incident_id DESC LIMIT 3"
        with connect_read_only(self.historical_database_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        similar = tuple({
            "incident_id": row["incident_id"], "facility_id": row["facility_id"],
            "severity": row["severity"], "recorded_root_cause": row["root_cause"],
            "downtime_minutes": row["downtime_minutes"], "status": row["status"],
            "similarity_basis": "same facility and/or severity only",
        } for row in rows)
        evidence = [EvidenceRecord(
            str(row["incident_id"]), "historical_incident", "uptime_incidents",
            str(row["start_time"]), str(row["facility_id"]), row["server_id"],
            "resolved_incident", {"root_cause_label": row["root_cause"], "downtime_minutes": row["downtime_minutes"]},
            str(row["severity"]), "Cautious analogue based only on explicit facility/severity overlap", "historical_analyst",
        ) for row in rows]
        ids = tuple(item.evidence_id for item in evidence)
        return similar, evidence, SpecialistFinding(
            "historical_analyst", f"Found {len(rows)} cautious historical analogues.", ids
        )

    def _maintenance_analyst(
        self, similar: tuple[dict[str, object], ...]
    ) -> tuple[tuple[str, ...], list[EvidenceRecord], SpecialistFinding]:
        incident_ids = [str(row["incident_id"]) for row in similar]
        if not incident_ids:
            return (), [], SpecialistFinding("maintenance_runbook_analyst", "No supported guidance found.", ())
        placeholders = ",".join("?" for _ in incident_ids)
        with connect_read_only(self.historical_database_path) as connection:
            rows = connection.execute(
                f"""SELECT action_id, incident_id, facility_id, server_id, timestamp,
                    action_type, result FROM maintenance_actions
                    WHERE incident_id IN ({placeholders}) ORDER BY timestamp DESC LIMIT 5""",
                incident_ids,
            ).fetchall()
        guidance = tuple(
            f"Consider operator review of prior action type '{row['action_type']}' from {row['incident_id']}; do not execute automatically."
            for row in rows
        )
        evidence = [EvidenceRecord(
            str(row["action_id"]), "maintenance_action", "maintenance_actions",
            str(row["timestamp"]), str(row["facility_id"]), row["server_id"],
            str(row["action_type"]), {"incident_id": row["incident_id"], "recorded_result": row["result"]},
            None, "Human-recorded action from a cautious historical analogue", "maintenance_runbook_analyst",
        ) for row in rows]
        return guidance, evidence, SpecialistFinding(
            "maintenance_runbook_analyst", f"Retrieved {len(rows)} supported prior actions; execution is disabled.",
            tuple(item.evidence_id for item in evidence),
        )

    def _hypothesis(
        self, evidence: tuple[EvidenceRecord, ...]
    ) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        domain_rows: dict[str, list[EvidenceRecord]] = {name: [] for name in self.DOMAIN_METRICS}
        domain_types: dict[str, set[str]] = {name: set() for name in self.DOMAIN_METRICS}
        evidence_weights = {
            "alert": 5, "anomaly": 4, "log": 3,
            "metric_change": 2, "historical_incident": 1,
        }
        for item in evidence:
            for domain, metrics in self.DOMAIN_METRICS.items():
                if item.metric_or_event in metrics:
                    domain_rows[domain].append(item)
                    domain_types[domain].add(item.evidence_type)
        # Repetition within one source type cannot overwhelm independent
        # corroboration from metrics, anomalies, alerts, and logs.
        domain_scores = {
            domain: sum(evidence_weights.get(kind, 1) for kind in types)
            + min(len(domain_rows[domain]), 3)
            for domain, types in domain_types.items()
        }
        ranked = sorted(
            domain_rows.items(),
            key=lambda item: (-domain_scores[item[0]], -len(item[1]), item[0]),
        )
        if not ranked or not ranked[0][1]:
            fallback = tuple(item.evidence_id for item in evidence[:1])
            return "No metric domain dominates the current evidence.", (), fallback
        best, rows = ranked[0]
        alternatives = tuple(
            f"{name.title()} degradation remains a possible co-contributor."
            for name, values in ranked[1:3] if values
        )
        return (
            f"{best.title()} degradation is the leading observed contributor.",
            alternatives,
            tuple(item.evidence_id for item in rows[:5]),
        )

    def _first_abnormal_signal(
        self, evidence: tuple[EvidenceRecord, ...], contributor: str
    ) -> EvidenceRecord | None:
        """Select the earliest current signal from the leading observed domain."""
        live_types = {"metric_change", "anomaly", "alert", "log"}
        leading_domain = next(
            (domain for domain in self.DOMAIN_METRICS if contributor.lower().startswith(domain)),
            None,
        )
        if leading_domain:
            for item in evidence:
                if (
                    item.evidence_type in live_types
                    and item.metric_or_event in self.DOMAIN_METRICS[leading_domain]
                ):
                    return item
        return next((item for item in evidence if item.evidence_type in live_types), None)

    @staticmethod
    def _confidence(
        evidence: tuple[EvidenceRecord, ...], route: str, verified: bool
    ) -> str:
        if not verified:
            return "INSUFFICIENT_EVIDENCE"
        source_types = {item.evidence_type for item in evidence}
        if {"metric_change", "anomaly", "alert"} <= source_types and route == "multi_agent":
            return "LIKELY"
        if len(source_types) >= 2:
            return "POSSIBLE"
        return "INSUFFICIENT_EVIDENCE"

    def _inspections(self, evidence: tuple[EvidenceRecord, ...]) -> tuple[str, ...]:
        metrics = {item.metric_or_event for item in evidence}
        checks: list[str] = []
        for domain, domain_metrics in self.DOMAIN_METRICS.items():
            if metrics & domain_metrics:
                checks.append(f"Have an operator inspect {domain} telemetry and physical controls for the affected scope.")
        checks.append("Confirm any intervention through the human approval workflow before execution.")
        return tuple(checks[:5])
