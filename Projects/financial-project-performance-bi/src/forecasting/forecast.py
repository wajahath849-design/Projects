from __future__ import annotations

import numpy as np
import pandas as pd

from src.utils.common import date_key, month_start


def forecast_costs(projects: pd.DataFrame, costs: pd.DataFrame, budgets: pd.DataFrame,
                   as_of: pd.Timestamp, trailing_months: int, scenarios: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Trailing spend rate times future months; snapshots are computed only from prior actuals."""
    monthly = costs.assign(month=costs.transaction_date.dt.to_period("M").dt.to_timestamp()).groupby(["project_id", "month"], as_index=False).amount.sum()
    latest_budget = budgets.groupby("project_id", as_index=False).allocated_budget_usd.sum().set_index("project_id").allocated_budget_usd
    rows, evaluations = [], []
    snapshot_months = [pd.Timestamp("2026-06-30"), as_of]
    for snapshot in snapshot_months:
        if snapshot > as_of:
            continue
        for p in projects.itertuples(index=False):
            history = monthly[(monthly.project_id == p.project_id) & (monthly.month <= month_start(snapshot))].sort_values("month")
            if history.empty:
                continue
            last_month = month_start(snapshot)
            window = pd.date_range(last_month - pd.DateOffset(months=trailing_months - 1), last_month, freq="MS")
            values = history.set_index("month").amount.reindex(window, fill_value=0.0)
            baseline = float(values.mean())
            completed = p.status == "Complete" and p.planned_end_date <= snapshot
            if completed:
                continue
            future = pd.date_range(last_month + pd.DateOffset(months=1), month_start(p.planned_end_date), freq="MS")
            if len(future) == 0:
                continue
            budget = float(latest_budget.get(p.project_id, np.nan))
            actual_to_date = float(history.amount.sum())
            # First six months use conservative planned burn if history is sparse.
            if len(history) < 3:
                duration = max(len(pd.date_range(month_start(p.start_date), month_start(p.planned_end_date), freq="MS")), 1)
                baseline = budget / duration
            for scenario, multiplier in scenarios.items():
                for month in future:
                    rows.append({"forecast_id": f"{p.project_id}-{snapshot:%Y%m%d}-{scenario}-{month:%Y%m}",
                        "project_id": p.project_id, "snapshot_date": snapshot.date(), "forecast_month": month.date(),
                        "date_key": date_key(month), "scenario": scenario, "forecast_cost_usd": round(baseline * multiplier, 2),
                        "is_latest_valid": snapshot == as_of, "baseline_monthly_usd": round(baseline, 2),
                        "actual_at_snapshot_usd": round(actual_to_date, 2), "approved_budget_usd": budget})
            if snapshot < as_of and len(future):
                observed = monthly[(monthly.project_id == p.project_id) & (monthly.month > last_month) &
                                   (monthly.month <= month_start(as_of))]
                if len(observed):
                    evaluations.append({"project_id": p.project_id, "snapshot_date": snapshot.date(),
                        "holdout_months": len(observed), "actual_usd": round(float(observed.amount.sum()), 2),
                        "baseline_forecast_usd": round(baseline * len(observed), 2),
                        "absolute_error_usd": round(abs(float(observed.amount.sum()) - baseline * len(observed)), 2)})
    return pd.DataFrame(rows), pd.DataFrame(evaluations)

