"""FastAPI-to-SQL Server integration tests for every read area."""

from __future__ import annotations

from fastapi.testclient import TestClient

from decision_intelligence.api.main import app

CLIENT = TestClient(app)


def test_health_and_openapi() -> None:
    assert CLIENT.get("/health").status_code == 200
    assert CLIENT.get("/health/database").json()["status"] == "healthy"
    assert CLIENT.get("/health/models").json()["status"] == "healthy"
    assert CLIENT.get("/openapi.json").status_code == 200


def test_forecast_inventory_and_recommendation_flows() -> None:
    forecast_response = CLIENT.get("/api/v1/forecasts?limit=2")
    assert forecast_response.status_code == 200
    forecasts = forecast_response.json()
    assert len(forecasts) == 2
    product_id = forecasts[0]["product_id"]
    assert CLIENT.get(f"/api/v1/forecasts/{product_id}").status_code == 200
    assert CLIENT.get("/api/v1/forecast-metrics").status_code == 200
    assert CLIENT.get("/api/v1/inventory/status").status_code == 200
    assert CLIENT.get("/api/v1/inventory/risks").status_code == 200
    assert CLIENT.get(f"/api/v1/inventory/{product_id}").status_code == 200
    recommendations = CLIENT.get("/api/v1/recommendations")
    assert recommendations.status_code == 200
    assert recommendations.json()
    recommended_product = recommendations.json()[0]["product_id"]
    assert CLIENT.get(
        f"/api/v1/recommendations/{recommended_product}"
    ).status_code == 200
    explanation = CLIENT.get(
        f"/api/v1/explanations/{forecasts[0]['forecast_id']}"
    )
    assert explanation.status_code == 200
    assert len(explanation.json()) == 5


def test_scenario_flow() -> None:
    scenarios = CLIENT.get("/api/v1/scenarios")
    assert scenarios.status_code == 200
    assert len(scenarios.json()) >= 10
    run = CLIENT.post("/api/v1/scenarios/demand_up/run")
    assert run.status_code == 200
    assert run.json()["records"] == 20
    results = CLIENT.get("/api/v1/scenarios/demand_up/results")
    assert results.status_code == 200
    assert len(results.json()) == 20
