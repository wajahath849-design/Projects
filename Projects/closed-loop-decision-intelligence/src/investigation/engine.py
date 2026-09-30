from datetime import timedelta

import pandas as pd

from src.common.config import read_config
from src.common.store import identity


def contributions(frame: pd.DataFrame, when, metric="revenue", dimensions=None) -> list[dict]:
    """Each dimension is a separate decomposition; never sum shares across dimensions.

    Denominator is gross absolute segment change, so offsetting gains do not inflate shares.
    """
    day = pd.Timestamp(when).normalize()
    current = frame[frame.timestamp.dt.normalize() == day]
    history = frame[(frame.timestamp < day) & (frame.timestamp >= day-pd.Timedelta(days=56))
                    & (frame.timestamp.dt.weekday == day.weekday())]
    periods = history.timestamp.dt.normalize().nunique()
    if not periods:
        return []
    result = []
    for dimension in dimensions or ["country_device", "country", "device", "channel", "product_category", "customer_segment", "campaign"]:
        baseline = history.groupby(dimension)[metric].sum()/periods
        actual = current.groupby(dimension)[metric].sum()
        delta = actual.subtract(baseline, fill_value=0)
        denominator = delta.abs().sum()
        for segment in delta.index:
            before, after = float(baseline.get(segment, 0)), float(actual.get(segment, 0))
            result.append(dict(dimension=dimension, segment=str(segment), metric=metric,
                current_value=after, baseline_value=before, difference=after-before,
                contribution=float(abs(after-before)/denominator) if denominator else 0,
                statistical_strength=float(min(1, abs(after-before)/max(before, 1))),
                description="Descriptive share of absolute segment change within this dimension; not causal attribution."))
    return sorted(result, key=lambda row: abs(row["difference"]), reverse=True)


def investigate(frame: pd.DataFrame, anomaly: dict, deployments: list[dict], context: list[dict]) -> dict:
    day = pd.Timestamp(anomaly["timestamp"]).normalize()
    current = frame[frame.timestamp.dt.normalize() == day]
    history = frame[(frame.timestamp < day) & (frame.timestamp >= day-pd.Timedelta(days=56))]
    def rate(data, numerator, denominator):
        return float(data[numerator].sum()/max(data[denominator].sum(), 1))
    signals = {"checkout_error_rate": rate(current, "checkout_errors", "attempts"),
               "payment_failure_rate": rate(current, "payment_failures", "payment_attempts"),
               "baseline_payment_failure_rate": rate(history, "payment_failures", "payment_attempts"),
               "tracking_ratio": rate(current, "sessions", "server_sessions")}
    observed_at = current.timestamp.max() if not current.empty else day
    recent = [d for d in deployments if timedelta(0) <= observed_at-pd.Timestamp(d["timestamp"]) <= timedelta(minutes=60)]
    signals["recent_deployments"] = [d["id"] for d in recent]
    signals["dependency_graph"] = read_config("anomaly_rules")["relationships"].get(anomaly["metric"], [])
    relevant = [c for c in context if timedelta(0) <= observed_at-pd.Timestamp(c["timestamp"]) <= timedelta(days=14)]
    signals["operational_context"] = [c["component"] for c in relevant]
    driver, confidence = "unknown", .35
    if anomaly["classification"] == "DATA_QUALITY" or signals["tracking_ratio"] < .5:
        driver, confidence = "tracking", .95
    elif recent and signals["checkout_error_rate"] > .08:
        driver, confidence = "deployment", .90
    elif signals["payment_failure_rate"] > max(.12, signals["baseline_payment_failure_rate"]*2):
        driver, confidence = "payment_provider", .80
    elif anomaly["metric"] == "cac":
        driver, confidence = "campaign_efficiency", .75
    elif "support" in signals["operational_context"] and anomaly["metric"] in ("churn", "support_volume"):
        driver, confidence = "support", .80
    elif "inventory" in signals["operational_context"] and anomaly["metric"] in ("orders", "revenue"):
        driver, confidence = "inventory", .75
    rows = contributions(frame, day)
    for row in rows:
        row.update(id=identity(anomaly["id"], row["dimension"], row["segment"]), incident_id=anomaly["id"],
                   evidence_type="CONTRIBUTION")
    for metric, baseline in [("payment_failure_rate", signals["baseline_payment_failure_rate"]),
                              ("checkout_error_rate", rate(history, "checkout_errors", "attempts")),
                              ("tracking_ratio", rate(history, "sessions", "server_sessions"))]:
        actual = signals[metric]
        rows.append(dict(id=identity(anomaly["id"], "signal", metric), incident_id=anomaly["id"],
                         evidence_type="CROSS_METRIC", dimension="all", segment="all", metric=metric,
                         current_value=actual, baseline_value=baseline, difference=actual-baseline,
                         contribution=0., statistical_strength=confidence,
                         description="Observed contemporaneous ratio and prior-history ratio; association, not causation."))
    return {"evidence": rows, "driver": driver, "confidence": confidence, "signals": signals,
            "description": f"Likely driver: {driver}. Temporal and cross-metric evidence supports a hypothesis, not proven causation."}
