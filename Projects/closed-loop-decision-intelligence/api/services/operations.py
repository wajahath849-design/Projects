"""Operational KPIs calculated from persisted stage and decision timestamps."""
from statistics import mean

from src.common import models as m
from src.common.store import records


def operating_metrics(connection) -> dict:
    incidents = records(connection, m.incidents)
    hypotheses = records(connection, m.hypotheses)
    recommendations = records(connection, m.recommendations)
    approvals = records(connection, m.approvals)
    actions = records(connection, m.actions)
    impacts = records(connection, m.actual_impacts)
    outcomes = records(connection, m.outcomes)
    runs = records(connection, m.pipeline_runs)
    quality = records(connection, m.data_quality_results)
    by_incident = {i["id"]: i for i in incidents}
    by_recommendation = {r["id"]: r for r in recommendations}
    by_action = {a["id"]: a for a in actions}

    def average(values):
        return mean(values) if values else None

    def ratio(numerator, denominator):
        return numerator/denominator if denominator else None

    def minutes(later, earlier):
        return max(0., (later-earlier).total_seconds()/60)

    terminal_approvals = [a for a in approvals if a["status"] in ("APPROVED", "REJECTED")]
    terminal_runs = [r for r in runs if r["status"] in ("SUCCESS", "FAILED")]
    metrics = {
        "mean_time_to_investigate_minutes": average([minutes(h["created_at"], by_incident[h["incident_id"]]["created_at"]) for h in hypotheses]),
        "mean_time_to_decision_minutes": average([minutes(r["created_at"], by_incident[r["incident_id"]]["created_at"]) for r in recommendations]),
        "mean_time_to_action_minutes": average([minutes(a["execution_time"], by_recommendation[a["recommendation_id"]]["created_at"]) for a in actions]),
        "mean_time_to_verify_minutes": average([minutes(i["created_at"], by_action[i["action_id"]]["execution_time"]) for i in impacts]),
        "approval_rate": ratio(sum(a["status"] == "APPROVED" for a in terminal_approvals), len(terminal_approvals)),
        "recommendation_success_rate": ratio(sum(o["outcome"] == "SUCCESS" for o in outcomes), len(outcomes)),
        "average_actual_impact": average([i["percentage_impact"] for i in impacts]),
        "expected_vs_actual_mean_absolute_error": average([abs(i["difference_from_expected"]) for i in impacts]),
        "incidents_automatically_investigated": len(hypotheses),
        "data_quality_failure_rate": ratio(sum(q["status"] == "FAIL" for q in quality), len(quality)),
        "workflow_success_rate": ratio(sum(r["status"] == "SUCCESS" for r in terminal_runs), len(terminal_runs)),
        "mean_time_to_detect_minutes": None,
        "anomaly_precision": None, "false_positive_rate": None, "revenue_protected": None,
        "unavailable_reasons": {
            "mean_time_to_detect_minutes": "Daily replay lacks a minute-resolution detection clock; see evaluation for bucket-level delay.",
            "anomaly_precision": "Only evaluation may access hidden labels; see the offline evaluation report.",
            "false_positive_rate": "Only evaluation may access hidden labels; see the offline evaluation report.",
            "revenue_protected": "Conversion recovery alone does not identify attributable monetary protection; no invented EUR estimate."},
    }
    return metrics
