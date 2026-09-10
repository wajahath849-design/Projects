"""Deterministic diagnostic confidence from explicit evidence coverage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConfidenceResult:
    level: str
    score: int
    maximum: int
    breakdown: dict[str, int]
    missing_evidence: list[str]


class DiagnosticConfidenceEngine:
    MAXIMUM = 9

    def calculate(
        self,
        correlated_metric_count: int,
        matching_log_code_count: int,
        alert_count: int,
        similar_incident_count: int,
        confirmed_maintenance_count: int,
        recorded_incident_category: bool,
    ) -> ConfidenceResult:
        breakdown = {
            "recorded_incident_category": 2 if recorded_incident_category else 0,
            "correlated_metrics": 2 if correlated_metric_count >= 2 else 1 if correlated_metric_count else 0,
            "matching_log_codes": 2 if matching_log_code_count >= 2 else 1 if matching_log_code_count else 0,
            "matching_alerts": 1 if alert_count else 0,
            "similar_incidents": 1 if similar_incident_count else 0,
            "confirmed_maintenance": 0,
        }
        if confirmed_maintenance_count:
            breakdown["confirmed_maintenance"] = 1
        score = min(self.MAXIMUM, sum(breakdown.values()))
        missing = [name for name, value in breakdown.items() if value == 0]
        level = "High" if score >= 7 else "Moderate" if score >= 4 else "Low"
        return ConfidenceResult(level, score, self.MAXIMUM, breakdown, missing)
