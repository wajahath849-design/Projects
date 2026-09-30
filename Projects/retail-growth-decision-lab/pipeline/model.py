"""Out-of-time repurchase prediction. Run: python -m pipeline.model.

Customer identities are never model features. Repeated customers across months are
intentional: the estimand is future purchases by known customers, not cold start.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "models"
FEATURES = ["recency_days", "orders_90d", "spend_90d", "orders_30d", "orders_prior_30d",
            "tenure_days", "purchase_days_90d", "order_value", "is_uk"]
TRAIN_DATES = ["2011-04-01", "2011-05-01", "2011-06-01", "2011-07-01", "2011-08-01"]
VALIDATION_DATE, CALIBRATION_DATE, TEST_DATE = "2011-09-01", "2011-10-01", "2011-11-01"


def build_features(orders: pd.DataFrame, cutoff: str, include_label: bool = True) -> pd.DataFrame:
    """Features use dates strictly before cutoff; labels use [cutoff, cutoff+30d)."""
    when = pd.Timestamp(cutoff)
    past = orders.loc[orders.invoice_date < when].sort_values(["invoice_date", "invoice_no"])
    grouped = past.groupby("customer_id")
    f = grouped.agg(first_purchase=("invoice_date", "min"), last_purchase=("invoice_date", "max"),
                    lifetime_aov=("revenue", "mean"), country=("country", "last"))
    f["recency_days"] = (when - f.last_purchase).dt.total_seconds() / 86400
    f["tenure_days"] = (when - f.first_purchase).dt.total_seconds() / 86400
    recent = past.loc[past.invoice_date >= when - pd.Timedelta(days=90)].copy()
    recent["purchase_day"] = recent.invoice_date.dt.normalize()
    stats = recent.groupby("customer_id").agg(orders_90d=("invoice_no", "size"),
        spend_90d=("revenue", "sum"), purchase_days_90d=("purchase_day", "nunique"), aov90=("revenue", "mean"))
    f = f.join(stats)
    for col in ["orders_90d", "spend_90d", "purchase_days_90d"]:
        f[col] = f[col].fillna(0)
    f["order_value"] = f.aov90.fillna(f.lifetime_aov)
    for col, start, end in [("orders_30d", 30, 0), ("orders_prior_30d", 60, 30)]:
        counts = past.loc[(past.invoice_date >= when - pd.Timedelta(days=start)) &
                          (past.invoice_date < when - pd.Timedelta(days=end))].groupby("customer_id").size()
        f[col] = counts.reindex(f.index, fill_value=0)
    f["is_uk"] = (f.country == "United Kingdom").astype(int)
    f["cutoff"] = cutoff
    f["feature_max_date"] = f.last_purchase
    if include_label:
        future = orders.loc[(orders.invoice_date >= when) & (orders.invoice_date < when + pd.Timedelta(days=30))]
        f["purchased"] = f.index.isin(future.customer_id).astype(int)
    return f.reset_index()


def design(frame: pd.DataFrame) -> pd.DataFrame:
    values = frame[FEATURES].copy()
    for col in FEATURES:
        if col != "is_uk":
            values[col] = np.log1p(values[col])
    return values


def metrics(y: np.ndarray, p: np.ndarray, name: str, split: str) -> dict:
    k = max(1, math.ceil(len(y) * .2))
    top = np.argsort(-p, kind="stable")[:k]
    rate = float(y.mean())
    return dict(model=name, split=split, n=len(y), prevalence=rate,
                roc_auc=float(roc_auc_score(y, p)), average_precision=float(average_precision_score(y, p)),
                brier=float(brier_score_loss(y, p)), precision_at_20=float(y[top].mean()),
                recall_at_20=float(y[top].sum() / y.sum()), lift_at_20=float(y[top].mean() / rate))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def recency_bin(frame):
    return np.digitize(frame.recency_days.to_numpy(), [7, 14, 30, 60, 90, 180])


def scenario(candidates: pd.DataFrame, budget=1000., cost=1., margin=.35, uplift=.03) -> dict:
    """Sensitivity scenario, NOT a causal estimate or estimated realized ROI."""
    if budget < 0 or cost <= 0 or not 0 <= margin <= 1 or not 0 <= uplift <= 1:
        raise ValueError("Budget >=0, cost >0, margin and absolute uplift within [0,1] required")
    ranked = candidates.sort_values(["priority_score", "customer_id"], ascending=[False, True])
    selected = ranked.head(min(len(ranked), int(budget // cost)))
    incremental_orders = np.minimum(uplift, 1 - selected.purchase_probability)
    gross_contribution = float((incremental_orders * selected.order_value * margin).sum())
    spend = len(selected) * cost
    return dict(selected_customers=len(selected), spend=spend, assumed_incremental_orders=float(incremental_orders.sum()),
                assumed_incremental_contribution=gross_contribution-spend, gross_contribution=gross_contribution)


def main():
    OUT.mkdir(exist_ok=True)
    orders = pd.read_csv(ROOT / "data/processed/orders.csv", dtype={"customer_id": str, "invoice_no": str})
    orders["invoice_date"] = pd.to_datetime(orders.invoice_date)
    # Complete Nov 1–Nov 30 outcome period is present in the source.
    if orders.invoice_date.max() < pd.Timestamp(TEST_DATE) + pd.Timedelta(days=30):
        raise ValueError("Test outcome window is not fully observed")
    train = pd.concat([build_features(orders, d) for d in TRAIN_DATES], ignore_index=True)
    valid, calibration, test = [build_features(orders, d) for d in [VALIDATION_DATE, CALIBRATION_DATE, TEST_DATE]]
    for frame in [train, valid, calibration, test]:
        assert (frame.feature_max_date < pd.to_datetime(frame.cutoff)).all()
        assert not frame.duplicated(["customer_id", "cutoff"]).any()
    candidates = {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=2000, random_state=42)),
        "Gradient boosting": HistGradientBoostingClassifier(max_iter=150, max_leaf_nodes=15, min_samples_leaf=40,
                                                           l2_regularization=5., learning_rate=.06, random_state=42),
    }
    rows, validation_scores = [], {}
    for name, model in candidates.items():
        model.fit(design(train), train.purchased)
        p = model.predict_proba(design(valid))[:, 1]
        row = metrics(valid.purchased.to_numpy(), p, name, "validation")
        rows.append(row)
        validation_scores[name] = row["average_precision"]
    chosen_name = max(validation_scores, key=validation_scores.get)
    chosen = candidates[chosen_name]
    # Independent October window fits probability calibration; November is untouched.
    calibrator = LogisticRegression(C=1e6, random_state=42)
    calibrator.fit(logit(chosen.predict_proba(design(calibration))[:, 1]), calibration.purchased)
    model_p = calibrator.predict_proba(logit(chosen.predict_proba(design(test))[:, 1]))[:, 1]
    # Recency-only lookup baseline is fitted on the same October calibration population.
    calibration["recency_bin"] = recency_bin(calibration)
    base_rate = float(calibration.purchased.mean())
    bins = calibration.groupby("recency_bin").purchased.agg(["sum", "count"])
    smoothed_rates = ((bins["sum"] + 20 * base_rate) / (bins["count"] + 20)).to_dict()
    recency_p = np.array([smoothed_rates.get(int(b), base_rate) for b in recency_bin(test)])
    # A compact RFM baseline uses only recency, 90-day frequency and monetary value.
    # It is fitted on the calibration month so it remains independent of the final test.
    rfm_features = ["recency_days", "orders_90d", "spend_90d"]
    rfm = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=2000, random_state=42))
    rfm.fit(np.log1p(calibration[rfm_features]), calibration.purchased)
    rfm_p = rfm.predict_proba(np.log1p(test[rfm_features]))[:, 1]
    y = test.purchased.to_numpy()
    predictions = {"Prevalence baseline": np.full(len(y), base_rate), "Recency baseline": recency_p,
                   "RFM baseline": rfm_p,
                   f"{chosen_name} (calibrated)": model_p}
    gains, calibration_rows = [], []
    for name, p in predictions.items():
        row = metrics(y, p, name, "test")
        if name == "Prevalence baseline":
            # No ranking exists for a constant score: expected random targeting values.
            row.update(precision_at_20=float(y.mean()), recall_at_20=math.ceil(len(y)*.2)/len(y), lift_at_20=1.)
        rows.append(row)
        for fraction in [.05, .1, .2, .3, .5, .75, 1.]:
            k = max(1, math.ceil(len(y) * fraction))
            selected = np.argsort(-p, kind="stable")[:k]
            precision = float(y[selected].mean()) if name != "Prevalence baseline" else float(y.mean())
            capture = float(y[selected].sum()/y.sum()) if name != "Prevalence baseline" else k/len(y)
            gains.append(dict(fraction=fraction, model=name, capture_rate=capture, precision=precision, lift=precision/y.mean()))
        binned = pd.DataFrame({"prediction":p,"outcome":y})
        binned["bin"] = pd.cut(binned.prediction, bins=np.linspace(0,1,11), labels=False, include_lowest=True)
        for bin_id, group in binned.groupby("bin", observed=True):
            calibration_rows.append(dict(bin=int(bin_id), model=name, mean_prediction=float(group.prediction.mean()),
                                         observed_rate=float(group.outcome.mean()), n=len(group)))
    # Bootstrap intervals quantify customer-sampling variation within November,
    # not seasonal uncertainty or causal effects. Paired differences use same resamples.
    rng = np.random.default_rng(42)
    aucs, aps, ap_diffs, ap_diffs_rfm = [], [], [], []
    for _ in range(400):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y[idx], model_p[idx]))
        ap = average_precision_score(y[idx], model_p[idx])
        aps.append(ap)
        ap_diffs.append(ap-average_precision_score(y[idx], recency_p[idx]))
        ap_diffs_rfm.append(ap-average_precision_score(y[idx], rfm_p[idx]))
    intervals = [{"metric": label, "low": float(np.quantile(values,.025)), "high":float(np.quantile(values,.975)),
                  "confidence":.95,"resamples":400} for label,values in
                 [("ROC AUC",aucs),("Average precision",aps),("AP difference vs recency",ap_diffs),
                  ("AP difference vs RFM",ap_diffs_rfm)]]
    # Cap estimated order value at TRAINING 95th percentile, avoiding future/outlier dominance.
    cap = float(train.order_value.quantile(.95))
    scored = test[["customer_id","country","recency_days","orders_90d","spend_90d","order_value"]].copy()
    scored["order_value"] = scored.order_value.clip(upper=cap)
    scored["purchase_probability"] = model_p
    scored["priority_score"] = scored.order_value * (1-model_p)
    scored["segment"] = np.select([scored.recency_days<=30,scored.recency_days<=90], ["Active","Cooling"],default="Dormant")
    scored = scored.sort_values(["priority_score","customer_id"], ascending=[False,True])
    scored.to_csv(OUT/"candidates.csv", index=False)
    test[["customer_id","cutoff","purchased"]].assign(prediction=model_p,recency_baseline=recency_p).to_csv(OUT/"test_predictions.csv", index=False)
    pd.DataFrame(rows).to_csv(OUT/"metrics.csv", index=False)
    pd.DataFrame(gains).to_csv(OUT/"gains.csv", index=False)
    pd.DataFrame(calibration_rows).to_csv(OUT/"calibration.csv", index=False)
    pd.DataFrame(intervals).to_csv(OUT/"intervals.csv", index=False)
    # Snapshot-level segment diagnostics (not protected demographic attributes).
    segment_rows=[]
    for segment in ["Active","Cooling","Dormant"]:
        mask = np.select([test.recency_days<=30,test.recency_days<=90],["Active","Cooling"],default="Dormant")==segment
        yy,pp=y[mask],model_p[mask]
        segment_rows.append(dict(segment=segment,n=int(mask.sum()),observed_rate=float(yy.mean()),mean_prediction=float(pp.mean()),brier=float(brier_score_loss(yy,pp))))
    pd.DataFrame(segment_rows).to_csv(OUT/"segments.csv",index=False)
    meta = dict(target="At least one valid positive purchase in the next 30 days",selected_model=chosen_name,
        selection_metric="September average precision",train_cutoffs=TRAIN_DATES,validation_cutoff=VALIDATION_DATE,
        calibration_cutoff=CALIBRATION_DATE,test_cutoff=TEST_DATE,test_end_exclusive="2011-12-01",
        train_rows=len(train),train_customers=int(train.customer_id.nunique()),test_customers=len(test),
        order_value_cap=cap,features=FEATURES,seed=42,bootstrap_resamples=400,default_scenario=scenario(scored),
        limitations=["One historical retailer with wholesalers; no modern-market generalization is established.",
        "Customer IDs excluded from predictors; known customers may recur across temporal windows.",
        "November seasonality may shift purchase rates. Bootstrap intervals exclude time-period uncertainty.",
        "Purchase propensity is not treatment uplift. No campaign assignment, cost or margin is observed.",
        "Priority is a value-times-nonpurchase heuristic, not an experimentally validated optimal policy.",
        "Order value is historical gross positive invoice value, capped at training P95; returns and margin are not learned."])
    (OUT/"model_card.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    joblib.dump(dict(model=chosen,calibrator=calibrator,features=FEATURES,cap=cap),OUT/"repurchase_model.joblib")
    print(json.dumps(dict(selected_model=chosen_name,test_metrics=rows[-3:],intervals=intervals,scenario=meta["default_scenario"]),indent=2))


if __name__ == "__main__":
    main()
