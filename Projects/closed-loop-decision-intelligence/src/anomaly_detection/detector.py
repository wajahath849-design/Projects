"""Seven-method ensemble with explicit business and quality gates.

Isolation Forest is trained once on the initial history, never on future points.
Scores and confidence are explainable heuristics, not calibrated probabilities.
"""
import numpy as np
import pandas as pd
from scipy.stats import binom, norm, poisson
from sklearn.ensemble import IsolationForest

from src.common.config import read_config
from src.common.store import identity
from src.metrics.engine import registry


def exposure_context(frame: pd.DataFrame, dimension: str) -> pd.DataFrame:
    """Aggregate event counts and denominators at exactly the monitored scope."""
    data = frame.copy()
    data["timestamp"] = data.timestamp.dt.normalize()
    data["dimension_value"] = "all" if dimension == "all" else data[dimension]
    columns = [c for c in ["orders", "sessions", "payment_failures", "payment_attempts",
                           "churned", "active_start", "new_customers", "tickets"] if c in data]
    return data.groupby(["timestamp", "dimension_value"])[columns].sum().reset_index()


def count_tail(metric: str, actual: float, expected: float, row, reference_n: float, historical_sd: float,
               uncertainty_sd: float = 2.) -> float:
    """Conservative count gate. Bounds account for estimated baseline uncertainty.

    This is a model-based tail test, not a causal probability or a calibrated false
    discovery rate. Sparse rates should not be declared incidents just for doubling.
    """
    rates = {"conversion": ("orders", "sessions", -1),
             "payment_failure_rate": ("payment_failures", "payment_attempts", 1),
             "churn": ("churned", "active_start", 1)}
    if metric in rates:
        numerator, denominator, direction = rates[metric]
        if numerator not in row or denominator not in row or reference_n <= 0:
            return 1.
        k, n = int(row[numerator]), int(row[denominator])
        if n <= 0 or not 0 < expected < 1:
            return 1.
        margin = uncertainty_sd*np.sqrt(expected*(1-expected)/reference_n)
        conservative_p = float(np.clip(expected+direction*margin, 1e-9, 1-1e-9))
        return float(binom.sf(k-1, n, conservative_p) if direction > 0 else binom.cdf(k, n, conservative_p))
    if metric == "cac":
        n = row.get("new_customers", 0)
        if n <= 0 or reference_n <= 0 or actual <= 0:
            return 1.
        return float(norm.sf(np.log(actual/expected)/np.sqrt(1/n+1/reference_n)))
    if metric in ("orders", "traffic", "support_volume"):
        direction = 1 if metric == "support_volume" else -1
        conservative_mean = max(.01, expected+direction*uncertainty_sd*historical_sd/2)
        return float(poisson.sf(int(actual)-1, conservative_mean) if direction > 0
                     else poisson.cdf(int(actual), conservative_mean))
    return 0.  # Revenue is continuous; its ensemble already checks dispersion.


def detect(observations: pd.DataFrame, tracking_days: set, promotions: set | None = None,
           frame: pd.DataFrame | None = None) -> list[dict]:
    rules = read_config("anomaly_rules")
    metrics = {m.metric_id: m for m in registry()}
    found = []
    selected = observations[observations.metric_id.isin(rules["alert_metrics"])]
    contexts = {d: exposure_context(frame, d) for d in selected.dimension_name.unique()} if frame is not None else {}
    for (metric_id, dimension, segment), group in selected.groupby(["metric_id", "dimension_name", "dimension_value"]):
        group = group.sort_values("timestamp").reset_index(drop=True)
        if contexts:
            group = group.merge(contexts[dimension], on=["timestamp", "dimension_value"], how="left", validate="one_to_one")
        denominator = {"conversion": "sessions", "payment_failure_rate": "payment_attempts",
                       "churn": "active_start", "cac": "new_customers"}.get(metric_id)
        reference_n = group[denominator].shift(1).rolling(28, min_periods=28).sum() if denominator in group else None
        x = group.actual_value.astype(float)
        previous = x.shift(1)
        mean = previous.rolling(28, min_periods=28).mean()
        std = previous.rolling(28, min_periods=28).std().clip(lower=.0001)
        median = previous.rolling(28, min_periods=28).median()
        mad = previous.rolling(28, min_periods=28).apply(lambda a: np.median(np.abs(a-np.median(a))), raw=True)
        ewma = previous.ewm(span=14, min_periods=28).mean()
        finite_train = x.iloc[:56].dropna().to_numpy().reshape(-1, 1)
        forest = None
        if len(finite_train) >= 28:
            forest = IsolationForest(n_estimators=40, random_state=42, contamination=.02, n_jobs=1).fit(finite_train)
        iso = np.zeros(len(x), dtype=bool)
        if forest is not None:
            eligible = x.notna() & (group.index >= 56)
            if eligible.any():
                iso[eligible] = forest.predict(x[eligible].to_numpy().reshape(-1, 1)) == -1
        direction = -1 if metrics[metric_id].direction == "up" else 1
        streak = 0
        for i, row in group.iterrows():
            actual, expected = row.actual_value, row.expected_value
            if i < 28 or not np.isfinite(actual) or not np.isfinite(expected) or expected <= 0:
                continue
            deviation = (actual-expected)/expected
            adverse = deviation*direction
            day = pd.Timestamp(row.timestamp).normalize()
            dq = day in tracking_days and metric_id in ("traffic", "conversion")
            planned = day in (promotions or set()) and adverse < 0
            if adverse < rules["minimum_deviation"] and not (dq and metric_id == "traffic"):
                streak = 0
                continue
            tail = count_tail(metric_id, actual, expected, row,
                              float(reference_n.iloc[i]) if reference_n is not None else 0.,
                              float(std.iloc[i]), rules["baseline_uncertainty_sd"]) if contexts else 0.
            if not dq and tail > rules["count_tail_probability"]:
                streak = 0
                continue
            streak += 1
            votes = {
                "static_threshold": bool(adverse > metrics[metric_id].critical_threshold),
                "rolling_z": bool(abs(actual-mean.iloc[i])/std.iloc[i] > rules["z_threshold"]),
                "robust_mad": bool(abs(actual-median.iloc[i])/max(1.4826*mad.iloc[i], expected*.025) > rules["mad_threshold"]),
                "rolling_baseline": bool(abs(actual-median.iloc[i])/max(abs(median.iloc[i]), .0001) > .25),
                "ewma": bool(abs(actual-ewma.iloc[i])/max(abs(ewma.iloc[i]), .0001) > .2),
                "seasonal": bool(adverse > .25), "isolation_forest": bool(iso[i])}
            statistical = sum(votes.values())/7
            score = min(1., .65*statistical + .25*min(adverse, 1) + .10*min(streak/3, 1))
            if (score < rules["minimum_score"] and not dq) or planned:
                continue
            classification = "DATA_QUALITY" if dq else "BUSINESS"
            votes["count_tail_probability"] = tail
            votes["count_gate_applied"] = bool(contexts)
            # One record per metric/segment/day; downstream incident coalescing uses a seven-day gap.
            found.append(dict(id=identity("anomaly", metric_id, row.timestamp, dimension, segment),
                metric=metric_id, timestamp=pd.Timestamp(row.timestamp).to_pydatetime(), dimension_name=dimension,
                dimension_value=segment, actual=float(actual), expected=float(expected), deviation=float(deviation),
                method=votes, anomaly_score=float(score), severity="CRITICAL" if score >= .85 else "HIGH",
                confidence=float(statistical*.95), data_quality_status="WARNING" if dq else "PASS",
                classification=classification))
    # Suppress misleading conversion alerts entirely during independently observed tracking failures.
    return [a for a in found if not (a["metric"] == "conversion" and pd.Timestamp(a["timestamp"]).normalize() in tracking_days)]
