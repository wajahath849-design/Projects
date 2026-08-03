"""SQL integration checks for inventory, optimization, scenarios, and reporting views."""

from __future__ import annotations

from pathlib import Path

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_inventory_optimization_and_scenarios_are_persisted() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        assert int(fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactStockoutRisk WHERE DataVersion='phase-11-v1'",
        )) == 20
        assert int(fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactOptimizationRecommendation
            WHERE DataVersion='phase-12-v1' AND SolverStatus IN ('OPTIMAL','FEASIBLE')""",
        )) >= 1
        assert int(fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactScenarioResult WHERE DataVersion='phase-13-v1'",
        )) == 200


def test_power_bi_views_are_queryable() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        views = int(fetch_scalar(
            connection, "SELECT COUNT(*) FROM sys.views WHERE name LIKE 'vw_PBI[_]%'"
        ))
        assert views == 8
        for view in (
            "vw_PBI_ExecutiveOverview", "vw_PBI_DemandForecast",
            "vw_PBI_InventoryIntelligence", "vw_PBI_OptimizationRecommendations",
            "vw_PBI_ScenarioComparison", "vw_PBI_ModelPerformance", "vw_PBI_DataQuality",
            "vw_PBI_ForecastExplanations",
        ):
            connection.execute(f"SELECT TOP 1 * FROM dbo.{view}").fetchone()
