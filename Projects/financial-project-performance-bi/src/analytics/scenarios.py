from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.common import path_from_config


def write_scenarios(curated: Path | None = None, output: Path | None = None) -> Path:
    curated = curated or path_from_config("curated_dir")
    output = output or Path(__file__).resolve().parents[2] / "docs/business_scenarios.md"
    metrics = pd.read_csv(curated / "ProjectMetrics.csv").set_index("project_id")
    costs = pd.read_csv(curated / "FactActualCost.csv")
    revenue = pd.read_csv(curated / "FactRevenue.csv")
    category = pd.read_csv(curated / "DimCostCategory.csv").set_index("category_id").category_name
    costs["month"] = costs.transaction_date.str[:7]
    revenue["month"] = revenue.recognition_date.str[:7]

    def money(value):
        return f"${value:,.2f}"

    def top_categories(pid, start=None):
        frame = costs[costs.project_id == pid]
        if start:
            frame = frame[frame.month >= start]
        totals = frame.groupby("category_id").amount.sum().sort_values(ascending=False).head(3)
        return ", ".join(f"{category[k]} {money(v)}" for k, v in totals.items())

    def top_transactions(pid, start=None):
        frame = costs[costs.project_id == pid]
        if start:
            frame = frame[frame.month >= start]
        frame = frame.nlargest(3, "amount")
        return "; ".join(f"{r.transaction_id} ({r.transaction_date}, {money(r.amount)})" for r in frame.itertuples())

    a, b, c = [metrics.loc[f"P{i:03}"] for i in (1, 2, 3)]
    bcost = costs[costs.project_id == "P002"].groupby("month").amount.sum()
    brev = revenue[revenue.project_id == "P002"].groupby("month").recognized_revenue_usd.sum()
    q1cost = bcost.loc["2026-01":"2026-03"].sum()
    q1rev = brev.loc["2026-01":"2026-03"].sum()
    q3cost = bcost.loc["2026-07":"2026-09"].sum()
    q3rev = brev.loc["2026-07":"2026-09"].sum()
    q1margin = (q1rev - q1cost) / q1rev
    q3margin = (q3rev - q3cost) / q3rev
    a_monthly = costs[costs.project_id == "P001"].groupby("month").amount.sum()
    lines = [
        "# Business scenarios — synthetic demonstration data",
        "", "All figures use the validated curated facts and the same project metrics as the dashboard. Data is fictional; actions are examples for management discussion, not actual company outcomes.",
        "", "## A. Confirmed over-budget project — P001", "",
        f"Approved budget {money(a.approved_budget_usd)}; actual cost {money(a.actual_cost_usd)}; unfavorable variance {money(-a.budget_variance_usd)} ({-a.budget_variance_pct:.1%} of budget).",
        f"The largest cost categories are {top_categories('P001')}. January–September 2026 cost totals {money(a_monthly.loc['2026-01':'2026-09'].sum())}; this is where the spend rate accelerated. Review transactions {top_transactions('P001', '2026-01')}.",
        "Management options: validate contractor scope and approvals, separate committed work from discretionary work, and rebaseline only after the commercial impact is approved.",
        "", "## B. Declining profitability — P002", "",
        f"Q1 2026 recognized revenue {money(q1rev)} against cost {money(q1cost)}, a {q1margin:.1%} margin. Q3 recognized revenue {money(q3rev)} against cost {money(q3cost)}, a {q3margin:.1%} margin. Lifetime margin is {b.gross_margin_pct:.1%}.",
        f"Since April 2026 the main cost contributors are {top_categories('P002', '2026-04')}. Example records: {top_transactions('P002', '2026-04')}. Both higher contractor costs and lower monthly recognition are visible in the synthetic source; this is a designed scenario, not a causal finding about a real business.",
        "Management options: review contract milestones and revenue recognition evidence, renegotiate supplier rates, and assess remaining work against expected contribution.",
        "", "## C. Forecasted overrun before the budget is breached — P003", "",
        f"Approved budget {money(c.approved_budget_usd)}; actual cost {money(c.actual_cost_usd)}; remaining approved budget {money(c.approved_budget_usd-c.actual_cost_usd)}. Base estimate to complete {money(c.estimate_to_complete_usd)} gives forecast at completion {money(c.estimate_at_completion_usd)} and expected overrun {money(c.forecast_overrun_usd)}.",
        f"Recent cost evidence: {top_categories('P003', '2026-07')}. Example records: {top_transactions('P003', '2026-07')}. The baseline extrapolates the trailing three months through the planned end date, so it is sensitive to staffing and schedule changes.",
        "Management options: confirm remaining deliverables and resource plan, compare optimistic and downside scenarios, and seek change control before the forecast becomes an actual overrun.",
        "", "## Reproduce", "", "Run `python run_pipeline.py --regenerate` and then `python -m src.analytics.scenarios`. The source facts and scenario figures share the same calculation path."
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(write_scenarios())
