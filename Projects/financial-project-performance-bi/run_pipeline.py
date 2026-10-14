from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analytics.metrics import project_metrics
from src.data_generation.generate import generate
from src.extraction.extract import read_sources
from src.forecasting.forecast import forecast_costs
from src.transformation.budget import select_approved_budget
from src.utils.common import date_key, path_from_config, settings
from src.validation.quality import assert_referential_integrity, clean_fact


def run(*, regenerate: bool = False, raw_dir: Path | None = None, curated_dir: Path | None = None,
        report_dir: Path | None = None) -> dict:
    cfg = settings()
    raw = raw_dir or path_from_config("raw_dir")
    curated = curated_dir or path_from_config("curated_dir")
    reports = report_dir or path_from_config("report_dir")
    if regenerate:
        generate(raw)
    source, metadata = read_sources(raw)
    projects = source["projects"].copy()
    for col in ("start_date", "planned_end_date"):
        projects[col] = pd.to_datetime(projects[col], errors="raise")
    projects["completion_pct"] = pd.to_numeric(projects.completion_pct, errors="raise")
    projects["contract_value_usd"] = pd.to_numeric(projects.contract_value_usd, errors="raise")
    if projects.project_id.duplicated().any():
        raise ValueError("Duplicate project identifier")
    if (projects.planned_end_date < projects.start_date).any():
        raise ValueError("Project end before start")
    departments, categories = source["departments"], source["categories"]
    budget, reject_b = clean_fact(source["budgets"], source="budgets", id_col="budget_record_id",
        amount_col="allocated_budget_usd", date_col="approved_date", projects=projects, departments=departments)
    cost, reject_c = clean_fact(source["costs"], source="costs", id_col="transaction_id",
        amount_col="amount", date_col="transaction_date", projects=projects, departments=departments, categories=categories)
    revenue, reject_r = clean_fact(source["revenue"], source="revenue", id_col="revenue_id",
        amount_col="recognized_revenue_usd", date_col="recognition_date", projects=projects)
    if not budget.version_number.notna().all():
        raise ValueError("Invalid budget version")
    budget["version_number"] = pd.to_numeric(budget.version_number, errors="raise").astype(int)
    selected_budget, versions = select_approved_budget(budget, pd.Timestamp(cfg["as_of_date"]))
    if set(projects.project_id) != set(selected_budget.project_id):
        raise ValueError("Every project must have an approved budget version")
    as_of = pd.Timestamp(cfg["as_of_date"])
    forecast, evaluation = forecast_costs(projects, cost, selected_budget, as_of,
        cfg["forecast_trailing_months"], cfg["forecast_scenarios"])
    budget["date_key"] = budget.approved_date.map(date_key)
    cost["date_key"] = cost.transaction_date.map(date_key)
    revenue["date_key"] = revenue.recognition_date.map(date_key)
    first = min(projects.start_date.min(), budget.approved_date.min())
    last = max(as_of + pd.DateOffset(months=36), projects.planned_end_date.max())
    dates = pd.DataFrame({"date": pd.date_range(first, last, freq="D")})
    dates["date_key"] = dates.date.map(date_key)
    dates["year"] = dates.date.dt.year
    dates["month_number"] = dates.date.dt.month
    dates["year_month"] = dates.date.dt.strftime("%Y-%m")
    dates["month_start"] = dates.date.dt.to_period("M").dt.to_timestamp()
    tables = {
        "DimProject": projects, "DimDate": dates, "DimDepartment": departments,
        "DimCostCategory": categories, "DimClient": source["clients"],
        "DimProjectManager": source["managers"], "DimBudgetVersion": versions,
        "FactBudget": budget, "FactActualCost": cost, "FactRevenue": revenue, "FactForecast": forecast,
    }
    assert_referential_integrity(tables)
    metrics = project_metrics(projects, selected_budget, cost, revenue, forecast)
    exceptions = pd.concat([reject_b, reject_c, reject_r], ignore_index=True)
    checks = {
        "budget_delta_usd": round(float(selected_budget.allocated_budget_usd.sum() - metrics.approved_budget_usd.sum()), 2),
        "actual_delta_usd": round(float(cost.amount.sum() - metrics.actual_cost_usd.sum()), 2),
        "revenue_delta_usd": round(float(revenue.recognized_revenue_usd.sum() - metrics.recognized_revenue_usd.sum()), 2),
        "orphan_count": 0,
    }
    if any(abs(v) > 0.01 for v in checks.values()):
        raise AssertionError(f"Reconciliation failed: {checks}")
    curated.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(curated / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    metrics.to_csv(curated / "ProjectMetrics.csv", index=False)
    exceptions.to_csv(reports / "data_quality_exceptions.csv", index=False)
    evaluation.to_csv(reports / "forecast_holdout.csv", index=False)
    pd.DataFrame(metadata).to_csv(reports / "source_manifest.csv", index=False)
    report = {"status": "success", "refreshed_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_classification": "synthetic demonstration data", "as_of_date": cfg["as_of_date"],
        "source_rows": {k: len(v) for k, v in source.items()}, "curated_rows": {k: len(v) for k, v in tables.items()},
        "rejected_rows": len(exceptions), "rejection_reasons": exceptions.reason.value_counts().to_dict(),
        "reconciliation": checks, "forecast_holdout_mae_usd": round(float(evaluation.absolute_error_usd.mean()), 2) if len(evaluation) else None}
    (reports / "refresh_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    logging.info(json.dumps({"event": "refresh_complete", "report": report}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--regenerate", action="store_true", help="Regenerate deterministic synthetic sources")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        print(json.dumps(run(regenerate=args.regenerate), indent=2))
    except Exception as exc:
        logging.error(json.dumps({"event": "refresh_failed", "error": str(exc)}))
        raise
