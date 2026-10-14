from __future__ import annotations

import numpy as np
import pandas as pd


def project_metrics(projects: pd.DataFrame, budget: pd.DataFrame, cost: pd.DataFrame,
                    revenue: pd.DataFrame, forecast: pd.DataFrame) -> pd.DataFrame:
    out = projects[["project_id", "project_name", "status", "completion_pct", "scenario_tag"]].copy()
    for source, column, target in [(budget, "allocated_budget_usd", "approved_budget_usd"),
                                   (cost, "amount", "actual_cost_usd"),
                                   (revenue, "recognized_revenue_usd", "recognized_revenue_usd")]:
        values = source.groupby("project_id")[column].sum().rename(target)
        out = out.join(values, on="project_id")
    base = forecast[(forecast.scenario == "base") & forecast.is_latest_valid]
    out = out.join(base.groupby("project_id").forecast_cost_usd.sum().rename("estimate_to_complete_usd"), on="project_id")
    out[["actual_cost_usd", "recognized_revenue_usd", "estimate_to_complete_usd"]] = out[["actual_cost_usd", "recognized_revenue_usd", "estimate_to_complete_usd"]].fillna(0)
    out["budget_variance_usd"] = out.approved_budget_usd - out.actual_cost_usd
    out["budget_variance_pct"] = out.budget_variance_usd / out.approved_budget_usd
    out["budget_utilization_pct"] = out.actual_cost_usd / out.approved_budget_usd
    out["gross_profit_usd"] = out.recognized_revenue_usd - out.actual_cost_usd
    out["gross_margin_pct"] = np.where(out.recognized_revenue_usd.ne(0), out.gross_profit_usd / out.recognized_revenue_usd, np.nan)
    out["estimate_at_completion_usd"] = out.actual_cost_usd + out.estimate_to_complete_usd
    out["forecast_overrun_usd"] = (out.estimate_at_completion_usd - out.approved_budget_usd).clip(lower=0)
    out["financial_health"] = np.select(
        [out.actual_cost_usd > out.approved_budget_usd, out.estimate_at_completion_usd > out.approved_budget_usd,
         out.gross_margin_pct < 0.15], ["Over budget", "At risk", "Low margin"], default="On track")
    return out.round(4)

