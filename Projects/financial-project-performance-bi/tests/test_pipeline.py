from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from run_pipeline import run
from src.analytics.metrics import project_metrics
from src.data_generation.generate import generate
from src.extraction.extract import read_sources
from src.forecasting.forecast import forecast_costs
from src.validation.quality import assert_referential_integrity, clean_fact
from src.utils.common import ROOT


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("financial_bi")
    raw, curated, reports = root / "raw", root / "curated", root / "reports"
    generate(raw)
    result = run(raw_dir=raw, curated_dir=curated, report_dir=reports)
    return raw, curated, reports, result


def table(built, name):
    return pd.read_csv(built[1] / f"{name}.csv")


def test_source_schema_missing_column(built, tmp_path):
    source = tmp_path / "raw"
    source.mkdir()
    for path in built[0].glob("*.csv"):
        (source / path.name).write_bytes(path.read_bytes())
    projects = pd.read_csv(source / "projects.csv").drop(columns="project_id")
    projects.to_csv(source / "projects.csv", index=False)
    with pytest.raises(ValueError, match="missing columns"):
        read_sources(source)


def test_excel_budget_source_matches_deterministic_csv(built, tmp_path):
    mirror = tmp_path / "excel_raw"
    mirror.mkdir()
    for path in built[0].glob("*.csv"):
        (mirror / path.name).write_bytes(path.read_bytes())
    (mirror / "budgets.xlsx").write_bytes((ROOT / "data/raw/budgets.xlsx").read_bytes())
    source, _ = read_sources(mirror)
    expected = pd.read_csv(built[0] / "budgets.csv")
    actual = source["budgets"].copy()
    assert len(actual) == len(expected)
    assert actual.budget_record_id.tolist() == expected.budget_record_id.tolist()
    assert pd.to_numeric(actual.allocated_budget_usd).sum() == pytest.approx(expected.allocated_budget_usd.sum())


def test_generated_quality_controls(built):
    exceptions = pd.read_csv(built[2] / "data_quality_exceptions.csv")
    assert set(exceptions.reason) == {"duplicate_identifier", "missing_project_identifier", "invalid_category", "date_before_project_start"}
    assert len(exceptions) == 4


def test_missing_identifier_and_invalid_date(built):
    sources, _ = read_sources(built[0])
    p = sources["projects"].copy()
    p.start_date = pd.to_datetime(p.start_date)
    sample = sources["costs"].iloc[:2].copy()
    sample.loc[sample.index[0], "transaction_id"] = ""
    sample.loc[sample.index[1], "transaction_date"] = "not a date"
    _, rejected = clean_fact(sample, source="costs", id_col="transaction_id", amount_col="amount",
        date_col="transaction_date", projects=p, departments=sources["departments"], categories=sources["categories"])
    assert set(rejected.reason) == {"missing_identifier", "invalid_date"}


def test_negative_corrections_preserved(built):
    fact = table(built, "FactActualCost")
    assert (fact.amount < 0).any()
    assert fact.transaction_id.is_unique


def test_referential_integrity(built):
    names = ["DimProject", "DimDate", "DimCostCategory", "DimDepartment", "FactBudget", "FactActualCost", "FactRevenue", "FactForecast"]
    assert_referential_integrity({name: table(built, name) for name in names})


def test_budget_version_selection(built):
    v = table(built, "DimBudgetVersion")
    assert v.groupby("project_id").is_selected_approved.sum().eq(1).all()
    assert v.loc[v.project_id == "P004"].sort_values("version_number").is_selected_approved.tolist() == [False, True]


def test_financial_reconciliation(built):
    report = built[3]
    assert report["reconciliation"] == {"budget_delta_usd": 0.0, "actual_delta_usd": 0.0,
                                         "revenue_delta_usd": 0.0, "orphan_count": 0}
    metric = table(built, "ProjectMetrics")
    actual = table(built, "FactActualCost")
    revenue = table(built, "FactRevenue")
    assert abs(metric.actual_cost_usd.sum() - actual.amount.sum()) < 0.01
    assert abs(metric.recognized_revenue_usd.sum() - revenue.recognized_revenue_usd.sum()) < 0.01


def test_variance_margin_and_forecast_formulas(built):
    metric = table(built, "ProjectMetrics")
    p = metric.set_index("project_id").loc["P001"]
    assert abs(p.budget_variance_usd - (p.approved_budget_usd - p.actual_cost_usd)) < 0.01
    assert abs(p.gross_margin_pct - (p.recognized_revenue_usd - p.actual_cost_usd) / p.recognized_revenue_usd) < 0.0001
    assert abs(p.estimate_at_completion_usd - (p.actual_cost_usd + p.estimate_to_complete_usd)) < 0.01
    assert abs(p.forecast_overrun_usd - max(0, p.estimate_at_completion_usd - p.approved_budget_usd)) < 0.01


def test_scenario_semantics(built):
    m = table(built, "ProjectMetrics").set_index("project_id")
    assert m.loc["P001", "actual_cost_usd"] > m.loc["P001", "approved_budget_usd"]
    assert m.loc["P003", "actual_cost_usd"] < m.loc["P003", "approved_budget_usd"]
    assert m.loc["P003", "forecast_overrun_usd"] > 0


def test_output_schema(built):
    assert {"project_id", "date_key", "category_id", "amount"} <= set(table(built, "FactActualCost"))
    assert {"project_id", "version_id", "department_id", "allocated_budget_usd"} <= set(table(built, "FactBudget"))
    assert {"project_id", "forecast_month", "scenario", "forecast_cost_usd"} <= set(table(built, "FactForecast"))


def test_idempotent_outputs(built):
    curated = built[1]
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in curated.glob("*.csv")}
    run(raw_dir=built[0], curated_dir=curated, report_dir=built[2])
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in curated.glob("*.csv")}
    assert before == after


def test_forecast_uses_prior_data_only(built):
    project = table(built, "DimProject")
    cost = table(built, "FactActualCost")
    budget = table(built, "FactBudget")
    project[["start_date", "planned_end_date"]] = project[["start_date", "planned_end_date"]].apply(pd.to_datetime)
    cost["transaction_date"] = pd.to_datetime(cost.transaction_date)
    selected = table(built, "DimBudgetVersion").query("is_selected_approved == True").version_id
    budget = budget[budget.version_id.isin(selected)]
    forecast, _ = forecast_costs(project, cost, budget, pd.Timestamp("2026-09-30"), 3, {"base": 1.0})
    old = forecast[(forecast.project_id == "P003") & (forecast.snapshot_date == pd.Timestamp("2026-06-30").date())]
    changed = cost.copy()
    changed.loc[changed.transaction_date >= pd.Timestamp("2026-08-01"), "amount"] *= 10
    forecast2, _ = forecast_costs(project, changed, budget, pd.Timestamp("2026-09-30"), 3, {"base": 1.0})
    old2 = forecast2[(forecast2.project_id == "P003") & (forecast2.snapshot_date == pd.Timestamp("2026-06-30").date())]
    assert old.forecast_cost_usd.tolist() == old2.forecast_cost_usd.tolist()
