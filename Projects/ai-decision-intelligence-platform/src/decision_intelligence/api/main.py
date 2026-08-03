"""FastAPI backend for forecasts, inventory, recommendations, scenarios, and explanations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, status

from decision_intelligence.api.dependencies import get_database_settings
from decision_intelligence.api.schemas import (
    ExplanationResponse,
    ForecastResponse,
    HealthResponse,
    InventoryResponse,
    MetricResponse,
    RecommendationResponse,
    RunResponse,
    ScenarioCreateRequest,
    ScenarioResponse,
    ScenarioResultResponse,
)
from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.forecasting.forecast_generator import generate_forecasts
from decision_intelligence.optimization import run_optimization
from decision_intelligence.scenarios import run_scenario as execute_scenario
from decision_intelligence.settings import DatabaseSettings

app = FastAPI(
    title="AI Decision Intelligence Platform API",
    version="1.0.0",
    description=(
        "Portfolio-grade API for measured demand forecasts, inventory risk, "
        "validated replenishment recommendations, scenarios, and explanations."
    ),
)

DatabaseDependency = Annotated[DatabaseSettings, Depends(get_database_settings)]


def _rows(settings: DatabaseSettings, query: str, *parameters: Any) -> list[dict[str, Any]]:
    with connect(settings) as connection:
        cursor = connection.execute(query, parameters)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    return HealthResponse(status="healthy", component="api")


@app.get("/health/database", response_model=HealthResponse, tags=["Health"])
def health_database(settings: DatabaseDependency) -> HealthResponse:
    try:
        with connect(settings) as connection:
            database = str(fetch_scalar(connection, "SELECT DB_NAME()"))
        return HealthResponse(status="healthy", component="database", detail=database)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


@app.get("/health/models", response_model=HealthResponse, tags=["Health"])
def health_models(settings: DatabaseDependency) -> HealthResponse:
    rows = _rows(
        settings,
        "SELECT ModelID model_id FROM dbo.DimModel WHERE IsProduction=1 AND ActiveFlag=1",
    )
    if len(rows) != 1:
        raise HTTPException(status_code=503, detail="Exactly one production model is required")
    return HealthResponse(
        status="healthy", component="models", detail=str(rows[0]["model_id"])
    )


FORECAST_QUERY = """SELECT TOP 1000 CONVERT(varchar(36),f.ForecastID) forecast_id,
  fd.FullDate forecast_date,td.FullDate target_date,p.ProductID product_id,
  s.StoreID store_id,m.ModelName model_name,f.HorizonDays horizon_days,
  f.ForecastQuantity forecast_quantity,f.LowerBound lower_bound,f.UpperBound upper_bound,
  f.ExpectedRevenue expected_revenue,f.ForecastBias forecast_bias,
  f.ForecastConfidence forecast_confidence,f.StockoutProbability stockout_probability
FROM dbo.FactForecast f JOIN dbo.DimDate fd ON fd.DateKey=f.ForecastDateKey
JOIN dbo.DimDate td ON td.DateKey=f.TargetDateKey
JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
LEFT JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
JOIN dbo.DimModel m ON m.ModelKey=f.ModelKey"""


@app.get("/api/v1/forecasts", response_model=list[ForecastResponse], tags=["Forecasting"])
def forecasts(
    settings: DatabaseDependency,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[dict[str, Any]]:
    return _rows(settings, FORECAST_QUERY + " ORDER BY td.FullDate,p.ProductID")[:limit]


@app.get(
    "/api/v1/forecasts/{product_id}",
    response_model=list[ForecastResponse],
    tags=["Forecasting"],
)
def forecasts_by_product(product_id: str, settings: DatabaseDependency) -> list[dict[str, Any]]:
    rows = _rows(
        settings, FORECAST_QUERY + " WHERE p.ProductID=? ORDER BY td.FullDate", product_id
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Product forecasts not found")
    return rows


@app.post("/api/v1/forecasts/run", response_model=RunResponse, tags=["Forecasting"])
def run_forecasts(settings: DatabaseDependency) -> RunResponse:
    project_root = Path(__file__).resolve().parents[3]
    result = generate_forecasts(
        settings,
        project_root / "data" / "processed" / "features" / "sample_features.parquet",
        project_root / "models" / "metadata" / "selected_model.json",
        project_root / "data" / "exports" / "forecasts",
    )
    return RunResponse(status="completed", records=len(result), detail="Forecast upsert complete")


@app.get(
    "/api/v1/forecast-metrics",
    response_model=list[MetricResponse],
    tags=["Forecasting"],
)
def forecast_metrics(settings: DatabaseDependency) -> list[dict[str, Any]]:
    return _rows(settings, """SELECT m.ModelID model_id,m.ModelName model_name,
      m.ModelVersion model_version,fm.HorizonDays horizon_days,fm.WAPE wape,
      fm.RMSE rmse,fm.MAE mae,fm.Bias bias,fm.SMAPE smape,
      mr.TrainingTimeSeconds training_time_seconds,
      mr.InferenceTimeSeconds inference_time_seconds,m.IsProduction is_production
    FROM dbo.FactForecastMetric fm JOIN dbo.DimModel m ON m.ModelKey=fm.ModelKey
    JOIN dbo.FactModelRun mr ON mr.ModelRunKey=fm.ModelRunKey
    WHERE fm.SourceSystem='FORECAST_TRAINING' ORDER BY mr.RunStartedAt DESC""")


INVENTORY_QUERY = """SELECT d.FullDate date,p.ProductID product_id,w.WarehouseID warehouse_id,
  r.CurrentInventory current_inventory,r.SafetyStock safety_stock,
  r.ReorderPoint reorder_point,r.ProjectedInventory projected_inventory,
  r.DaysOfSupply days_of_supply,r.StockoutProbability stockout_probability,
  r.RiskClassification risk_classification
FROM dbo.FactStockoutRisk r JOIN dbo.DimDate d ON d.DateKey=r.DateKey
JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey"""


@app.get("/api/v1/inventory/status", response_model=list[InventoryResponse], tags=["Inventory"])
def inventory_status(settings: DatabaseDependency) -> list[dict[str, Any]]:
    return _rows(settings, INVENTORY_QUERY + " ORDER BY r.RiskClassification,p.ProductID")


@app.get("/api/v1/inventory/risks", response_model=list[InventoryResponse], tags=["Inventory"])
def inventory_risks(settings: DatabaseDependency) -> list[dict[str, Any]]:
    return _rows(
        settings,
        INVENTORY_QUERY + " WHERE r.RiskClassification IN ('Critical','At Risk') "
        "ORDER BY r.StockoutProbability DESC",
    )


@app.get(
    "/api/v1/inventory/{product_id}",
    response_model=list[InventoryResponse],
    tags=["Inventory"],
)
def inventory_by_product(product_id: str, settings: DatabaseDependency) -> list[dict[str, Any]]:
    rows = _rows(settings, INVENTORY_QUERY + " WHERE p.ProductID=?", product_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Product inventory not found")
    return rows


RECOMMENDATION_QUERY = """SELECT CONVERT(varchar(36),r.RecommendationID) recommendation_id,
  p.ProductID product_id,s.SupplierID supplier_id,w.WarehouseID warehouse_id,
  r.RecommendedOrderQuantity recommended_order_quantity,
  od.FullDate recommended_order_date,ed.FullDate expected_delivery_date,
  r.ExpectedTotalCost expected_total_cost,
  r.ExpectedRevenueProtected expected_revenue_protected,
  r.ExpectedStockoutReduction expected_stockout_reduction,
  r.RecommendationPriority recommendation_priority,r.SolverStatus solver_status,
  r.DiagnosticMessage diagnostic_message
FROM dbo.FactOptimizationRecommendation r
JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey
JOIN dbo.DimSupplier s ON s.SupplierKey=r.SupplierKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey
JOIN dbo.DimDate od ON od.DateKey=r.RecommendedOrderDateKey
JOIN dbo.DimDate ed ON ed.DateKey=r.ExpectedDeliveryDateKey"""


@app.get(
    "/api/v1/recommendations",
    response_model=list[RecommendationResponse],
    tags=["Recommendations"],
)
def recommendations(settings: DatabaseDependency) -> list[dict[str, Any]]:
    return _rows(
        settings, RECOMMENDATION_QUERY + " ORDER BY r.RecommendationPriority,p.ProductID"
    )


@app.get(
    "/api/v1/recommendations/{product_id}",
    response_model=list[RecommendationResponse],
    tags=["Recommendations"],
)
def recommendations_by_product(
    product_id: str,
    settings: DatabaseDependency,
) -> list[dict[str, Any]]:
    rows = _rows(settings, RECOMMENDATION_QUERY + " WHERE p.ProductID=?", product_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Product recommendations not found")
    return rows


@app.post(
    "/api/v1/recommendations/run",
    response_model=RunResponse,
    tags=["Recommendations"],
)
def run_recommendations(settings: DatabaseDependency) -> RunResponse:
    project_root = Path(__file__).resolve().parents[3]
    solution = run_optimization(
        settings,
        project_root / "config" / "optimization.yaml",
        project_root / "data" / "exports" / "optimization",
    )
    return RunResponse(
        status=solution.status,
        records=len(solution.orders),
        detail="Constraint-validated recommendation upsert complete",
    )


@app.get(
    "/api/v1/scenarios",
    response_model=list[ScenarioResponse],
    tags=["Scenarios"],
)
def scenarios(settings: DatabaseDependency) -> list[dict[str, Any]]:
    return _rows(settings, """SELECT ScenarioID scenario_id,ScenarioName scenario_name,
      ScenarioType scenario_type,ParameterName parameter_name,BaselineValue baseline_value,
      ScenarioValue scenario_value,CreatedAt created_at FROM dbo.DimScenario
      WHERE DataVersion='phase-13-v1' ORDER BY ScenarioID""")


@app.post(
    "/api/v1/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scenarios"],
)
def create_scenario(
    request: ScenarioCreateRequest,
    settings: DatabaseDependency,
) -> dict[str, Any]:
    with connect(settings) as connection:
        exists = int(fetch_scalar(
            connection, "SELECT COUNT(*) FROM dbo.DimScenario WHERE ScenarioID=?",
            request.scenario_id,
        ))
        if exists:
            raise HTTPException(status_code=409, detail="Scenario ID already exists")
        connection.execute(
            """INSERT dbo.DimScenario
            (ScenarioID,ScenarioName,ScenarioType,ParameterName,BaselineValue,ScenarioValue,
             IsBaseline,SourceSystem,DataVersion) VALUES (?,?,?,?,?,?,0,?,?)""",
            request.scenario_id, request.scenario_name, request.scenario_type,
            request.parameter_name, request.baseline_value, request.scenario_value,
            "SCENARIO_API", "phase-13-v1",
        )
        connection.commit()
    rows = _rows(settings, """SELECT ScenarioID scenario_id,ScenarioName scenario_name,
      ScenarioType scenario_type,ParameterName parameter_name,BaselineValue baseline_value,
      ScenarioValue scenario_value,CreatedAt created_at FROM dbo.DimScenario
      WHERE ScenarioID=?""", request.scenario_id)
    return rows[0]


@app.post(
    "/api/v1/scenarios/{scenario_id}/run",
    response_model=RunResponse,
    tags=["Scenarios"],
)
def run_scenario(scenario_id: str, settings: DatabaseDependency) -> RunResponse:
    try:
        result = execute_scenario(settings, scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunResponse(
        status="completed", records=len(result), detail=f"Scenario {scenario_id} persisted"
    )


@app.get(
    "/api/v1/scenarios/{scenario_id}/results",
    response_model=list[ScenarioResultResponse],
    tags=["Scenarios"],
)
def scenario_results(
    scenario_id: str,
    settings: DatabaseDependency,
) -> list[dict[str, Any]]:
    rows = _rows(settings, """SELECT sc.ScenarioID scenario_id,p.ProductID product_id,
      w.WarehouseID warehouse_id,sr.ScenarioDemand-sr.BaselineDemand demand_impact,
      sr.ScenarioRevenue-sr.BaselineRevenue revenue_impact,
      sr.ScenarioTotalCost-sr.BaselineTotalCost cost_impact,
      sr.ScenarioProfit-sr.BaselineProfit profit_impact,
      sr.ScenarioStockoutProbability-sr.BaselineStockoutProbability stockout_impact,
      sr.RevenueProtected revenue_protected
    FROM dbo.FactScenarioResult sr JOIN dbo.DimScenario sc ON sc.ScenarioKey=sr.ScenarioKey
    LEFT JOIN dbo.DimProduct p ON p.ProductKey=sr.ProductKey
    LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey=sr.WarehouseKey
    WHERE sc.ScenarioID=? ORDER BY p.ProductID,w.WarehouseID""", scenario_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Scenario results not found")
    return rows


@app.get(
    "/api/v1/explanations/{forecast_id}",
    response_model=list[ExplanationResponse],
    tags=["Explainability"],
)
def explanations(forecast_id: uuid.UUID, settings: DatabaseDependency) -> list[dict[str, Any]]:
    rows = _rows(settings, """SELECT CONVERT(varchar(36),f.ForecastID) forecast_id,
      e.FeatureName feature_name,e.FeatureValue feature_value,e.ShapValue shap_value,
      e.ContributionRank contribution_rank,e.Direction direction,
      e.ExplanationText explanation_text
    FROM dbo.FactModelExplanation e JOIN dbo.FactForecast f ON f.ForecastKey=e.ForecastKey
    WHERE f.ForecastID=? ORDER BY e.ContributionRank""", str(forecast_id))
    if not rows:
        raise HTTPException(status_code=404, detail="Forecast explanations not found")
    return rows
