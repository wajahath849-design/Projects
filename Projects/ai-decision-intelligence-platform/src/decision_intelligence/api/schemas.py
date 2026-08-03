"""Pydantic request and response contracts for every API area."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from decision_intelligence.scenarios.engine import SUPPORTED_SCENARIOS


class HealthResponse(BaseModel):
    status: str
    component: str
    detail: str | None = None


class RunResponse(BaseModel):
    status: str
    records: int
    detail: str


class ForecastResponse(BaseModel):
    forecast_id: str
    forecast_date: date
    target_date: date
    product_id: str
    store_id: str | None
    model_name: str
    horizon_days: int
    forecast_quantity: float
    lower_bound: float | None
    upper_bound: float | None
    expected_revenue: float | None
    forecast_bias: float | None
    forecast_confidence: float | None
    stockout_probability: float | None


class MetricResponse(BaseModel):
    model_id: str
    model_name: str
    model_version: str
    horizon_days: int
    wape: float | None
    rmse: float | None
    mae: float | None
    bias: float | None
    smape: float | None
    training_time_seconds: float | None
    inference_time_seconds: float | None
    is_production: bool


class InventoryResponse(BaseModel):
    date: date
    product_id: str
    warehouse_id: str
    current_inventory: float
    safety_stock: float
    reorder_point: float
    projected_inventory: float | None
    days_of_supply: float | None
    stockout_probability: float
    risk_classification: str


class RecommendationResponse(BaseModel):
    recommendation_id: str
    product_id: str
    supplier_id: str
    warehouse_id: str
    recommended_order_quantity: float
    recommended_order_date: date
    expected_delivery_date: date
    expected_total_cost: float
    expected_revenue_protected: float
    expected_stockout_reduction: float
    recommendation_priority: str
    solver_status: str
    diagnostic_message: str | None


class ScenarioCreateRequest(BaseModel):
    scenario_id: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    scenario_name: str = Field(min_length=2, max_length=150)
    scenario_type: str
    parameter_name: str = Field(min_length=2, max_length=100)
    baseline_value: float
    scenario_value: float

    @field_validator("scenario_type")
    @classmethod
    def supported_type(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in SUPPORTED_SCENARIOS:
            raise ValueError(f"scenario_type must be one of {sorted(SUPPORTED_SCENARIOS)}")
        return normalized


class ScenarioResponse(BaseModel):
    scenario_id: str
    scenario_name: str
    scenario_type: str
    parameter_name: str
    baseline_value: float
    scenario_value: float
    created_at: datetime


class ScenarioResultResponse(BaseModel):
    scenario_id: str
    product_id: str | None
    warehouse_id: str | None
    demand_impact: float
    revenue_impact: float
    cost_impact: float
    profit_impact: float
    stockout_impact: float
    revenue_protected: float


class ExplanationResponse(BaseModel):
    forecast_id: str
    feature_name: str
    feature_value: str | None
    shap_value: float
    contribution_rank: int
    direction: str
    explanation_text: str | None
