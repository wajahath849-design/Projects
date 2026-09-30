"""Source checks plus scoped tracking suppression; no ground truth dependency."""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from src.common.store import identity, new_id


@dataclass
class QualityReport:
    checks: list[dict]
    tracking_days: set
    quarantined: bool


def validate(frames: dict, as_of=None) -> QualityReport:
    checks = []
    run_id = new_id()

    def add(dataset, kind, passed, actual, expected, severity="CRITICAL", details=None, column=None):
        checks.append(dict(id=identity(run_id, dataset, kind, column), run_id=run_id, dataset=dataset,
            check_type=kind, status="PASS" if passed else "FAIL" if severity == "CRITICAL" else "WARNING",
            severity=severity, column_name=column, actual_value=str(actual), expected_value=str(expected),
            details=details or {}))

    required = {"web_sessions": {"id", "timestamp", "sessions", "server_sessions", "country", "device", "channel"},
                "orders": {"id", "cohort_id", "customer_id", "amount", "status"},
                "payments": {"id", "order_id", "status"}}
    for name, columns in required.items():
        frame = frames.get(name, pd.DataFrame())
        valid_schema = columns <= set(frame.columns)
        add(name, "schema_drift", valid_schema, sorted(frame.columns), sorted(columns))
        if not valid_schema:
            return QualityReport(checks, set(), True)
        add(name, "completeness", not frame.empty, len(frame), ">0")
        add(name, "duplicates", not frame.id.duplicated().any(), int(frame.id.duplicated().sum()), 0)
        nulls = int(frame[list(columns)].isna().sum().sum())
        add(name, "null_rate", nulls == 0, nulls, 0)
    s, o, p = frames["web_sessions"], frames["orders"], frames["payments"]
    if s.empty:
        return QualityReport(checks, set(), True)
    stamps = pd.to_datetime(s.timestamp)
    watermark = pd.Timestamp(as_of) if as_of is not None else stamps.max()
    age = (watermark-stamps.max()).total_seconds()/3600
    add("web_sessions", "freshness", 0 <= age <= 36, age, "0..36 hours")
    add("orders", "referential_integrity", set(o.cohort_id) <= set(s.id),
        len(set(o.cohort_id)-set(s.id)), 0)
    add("payments", "referential_integrity", set(p.order_id) == set(o.id),
        len(set(p.order_id)^set(o.id)), 0)
    add("orders", "impossible_values", bool((o.amount >= 0).all()), int((o.amount < 0).sum()), 0)
    add("web_sessions", "impossible_values", bool((s.sessions >= 0).all()), int((s.sessions < 0).sum()), 0)
    daily = s.assign(day=stamps.dt.normalize()).groupby("day").agg(
        sessions=("sessions", "sum"), server=("server_sessions", "sum"), rows=("id", "count"))
    missing = len(pd.date_range(daily.index.min(), daily.index.max()).difference(daily.index))
    add("web_sessions", "metric_continuity", missing == 0, missing, 0)
    bad_rows = daily.rows < daily.rows.median()*.8
    add("web_sessions", "abnormal_row_count", not bad_rows.any(), int(bad_rows.sum()), 0)
    # Independent server traffic is an observed source, never a scenario label.
    ratios = daily.sessions/daily.server.replace(0, np.nan)
    tracking_days = set(daily.index[ratios < .5])
    add("web_sessions", "tracking_reconciliation", not tracking_days, len(tracking_days), 0,
        severity="HIGH", details={"suppressed_days": sorted(str(x.date()) for x in tracking_days),
                                   "scope": "traffic and conversion; orders and revenue remain observable"})
    weekly_ratio = daily.server / daily.server.shift(7).replace(0, np.nan)
    add("web_sessions", "abnormal_volume", not ((weekly_ratio < .3) | (weekly_ratio > 3)).any(),
        int(((weekly_ratio < .3) | (weekly_ratio > 3)).sum()), "within 0.3..3 of prior week", "HIGH")
    if len(daily) >= 56:
        drift = ks_2samp(daily.server.iloc[-28:], daily.server.iloc[-56:-28])
        add("web_sessions", "distribution_shift", drift.pvalue >= .01, float(drift.pvalue), ">=0.01", "MEDIUM")
    quarantined = any(c["status"] == "FAIL" and c["severity"] == "CRITICAL" for c in checks)
    return QualityReport(checks, tracking_days, quarantined)
