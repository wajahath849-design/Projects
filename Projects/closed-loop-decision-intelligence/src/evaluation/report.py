"""Evaluate observed alerts against hidden episodes without feeding labels back."""
import json

import pandas as pd
from sqlalchemy import select

from src.common import models as m
from src.common.config import ROOT
from src.common.store import records

# Evaluation-only relevance map; driver predictions are not part of detection matching.
RELEVANT = {
    "deployment": {"revenue", "orders", "conversion", "payment_failure_rate"},
    "campaign_efficiency": {"cac"}, "inventory": {"revenue", "orders", "conversion"},
    "support": {"support_volume", "churn"},
    "payment_provider": {"payment_failure_rate", "revenue", "orders", "conversion"},
    "tracking": {"traffic"},
}


def evaluate(engine) -> dict:
    with engine.connect() as connection:
        truths = records(connection, m.simulation_ground_truth)
        all_alerts = records(connection, m.anomalies)
        alerts = [a for a in all_alerts if a["dimension_name"] == "all"]
        incidents = records(connection, m.incidents)
        observed = pd.read_sql(select(m.metric_observations.c.metric_id, m.metric_observations.c.timestamp)
                              .where(m.metric_observations.c.dimension_name == "all"), connection)
    truths = [r for r in truths if r["incident_type"] != "planned"]

    def matches(alert, truth):
        day = pd.Timestamp(alert.get("timestamp", alert.get("detected_at"))).normalize()
        dimension, value = alert.get("dimension_name", "all"), alert.get("dimension_value", "all")
        scope_map = {"country": "affected_country", "device": "affected_device",
                     "channel": "affected_channel", "product_category": "affected_product"}
        if dimension in scope_map and truth[scope_map[dimension]] not in ("*", value):
            return False
        if dimension == "country_device":
            country, device = value.split(" / ")
            if truth["affected_country"] not in ("*", country) or truth["affected_device"] not in ("*", device):
                return False
        return (pd.Timestamp(truth["start_time"]).normalize() <= day <= pd.Timestamp(truth["end_time"]).normalize()
                and alert["metric"] in RELEVANT[truth["true_driver"]])

    matched = [a for a in alerts if any(matches(a, t) for t in truths)]
    all_matched = [a for a in all_alerts if any(matches(a, t) for t in truths)]
    correct_drivers, correct_severity, detected, delays = 0, 0, 0, []
    episodes = []
    for truth in truths:
        signals = sorted([a for a in all_alerts if matches(a, truth)], key=lambda a: a["timestamp"])
        hypotheses = [i for i in incidents if matches(i, truth)]
        identified = any(i["driver"] == truth["true_driver"] for i in hypotheses)
        if signals:
            detected += 1
            delay = max(0., (pd.Timestamp(signals[0]["timestamp"]).normalize()
                            -pd.Timestamp(truth["start_time"]).normalize()).total_seconds()/3600)
            delays.append(delay)
            correct_drivers += int(identified)
            correct_severity += int(signals[0]["severity"] == truth["severity"])
        episodes.append({"incident_id": truth["id"], "driver": truth["true_driver"], "detected": bool(signals),
                         "driver_identified": identified, "first_alert": str(signals[0]["timestamp"]) if signals else None})
    monitored = set().union(*RELEVANT.values())
    grid = observed[observed.metric_id.isin(monitored)].drop_duplicates()
    # Cold-start periods cannot alert; exclude the first 28 days from the negative denominator.
    if not grid.empty:
        grid["timestamp"] = pd.to_datetime(grid.timestamp)
        grid = grid[grid.timestamp >= grid.timestamp.min()+pd.Timedelta(days=28)]
    negatives = sum(not any(matches({"timestamp": row.timestamp, "metric": row.metric_id}, t) for t in truths)
                    for row in grid.itertuples())
    false_positives = len(alerts)-len(matched)
    report = {"evaluation_unit": "precision/FPR: global metric-day alerts; recall: episodes across all monitored scopes",
        "total_simulated_incidents": len(truths), "detected_incidents": detected,
        "true_positive_alerts": len(matched), "false_positive_alerts": false_positives,
        "precision": len(matched)/len(alerts) if alerts else None,
        "all_scope_alert_precision": len(all_matched)/len(all_alerts) if all_alerts else None,
        "all_scope_true_positive_alerts": len(all_matched),
        "all_scope_false_positive_alerts": len(all_alerts)-len(all_matched),
        "recall": detected/len(truths) if truths else None,
        "false_positive_rate": false_positives/negatives if negatives else None,
        "negative_metric_days": negatives,
        "mean_detection_delay_hours": sum(delays)/len(delays) if delays else None,
        "driver_identification_accuracy": correct_drivers/detected if detected else None,
        "severity_exact_match_accuracy": correct_severity/detected if detected else None,
        "episodes": episodes,
        "limitations": ["Single synthetic seed is a smoke evaluation, not external validation.",
                        "Daily aggregation cannot resolve minute-level detection delay.",
                        "Global alert precision counts repeated days; all-scope recall counts distinct hidden episodes.",
                        "Development-seed evaluation; scope policy was revised after inspecting missed inventory coverage.",
                        "Observational evidence supports hypotheses, not causal identification."]}
    path = ROOT / "data/exports/evaluation.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# Synthetic incident evaluation", "", "Computed from persisted observations and isolated ground truth.", ""]
    lines += [f"- {key}: {value}" for key, value in report.items() if key not in ("episodes", "limitations")]
    lines += ["", "| Episode | Driver | Detected | Driver identified |", "|---|---|---|---|"]
    lines += [f"| {r['incident_id']} | {r['driver']} | {r['detected']} | {r['driver_identified']} |" for r in episodes]
    lines += ["", *report["limitations"]]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/evaluation.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    return report
