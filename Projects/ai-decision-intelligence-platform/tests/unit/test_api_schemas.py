"""API schema, OpenAPI, and run-endpoint contract tests without external I/O."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from decision_intelligence.api.dependencies import get_database_settings
from decision_intelligence.api.main import app
from decision_intelligence.api.schemas import ScenarioCreateRequest
from decision_intelligence.optimization.optimizer import OptimizationSolution
from decision_intelligence.settings import DatabaseSettings


def _settings() -> DatabaseSettings:
    return DatabaseSettings("test", "test", "driver", True, True, 1, 1)


def test_scenario_schema_rejects_unsupported_type() -> None:
    with pytest.raises(ValidationError):
        ScenarioCreateRequest(
            scenario_id="bad", scenario_name="Bad scenario", scenario_type="UNKNOWN",
            parameter_name="factor", baseline_value=1, scenario_value=2,
        )


def test_openapi_contains_every_required_endpoint() -> None:
    paths = app.openapi()["paths"]
    required = {
        "/health", "/health/database", "/health/models", "/api/v1/forecasts",
        "/api/v1/forecasts/{product_id}", "/api/v1/forecasts/run",
        "/api/v1/forecast-metrics", "/api/v1/inventory/status",
        "/api/v1/inventory/risks", "/api/v1/inventory/{product_id}",
        "/api/v1/recommendations", "/api/v1/recommendations/{product_id}",
        "/api/v1/recommendations/run", "/api/v1/scenarios",
        "/api/v1/scenarios/{scenario_id}/run",
        "/api/v1/scenarios/{scenario_id}/results",
        "/api/v1/explanations/{forecast_id}",
    }
    assert required <= set(paths)


def test_run_endpoints_return_typed_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    from decision_intelligence.api import main

    app.dependency_overrides[get_database_settings] = _settings
    monkeypatch.setattr(main, "generate_forecasts", lambda *args: pd.DataFrame([{"x": 1}]))
    monkeypatch.setattr(
        main, "run_optimization",
        lambda *args: OptimizationSolution("OPTIMAL", 1.0, pd.DataFrame([{"x": 1}]), ()),
    )
    monkeypatch.setattr(main, "execute_scenario", lambda *args: pd.DataFrame([{"x": 1}]))
    client = TestClient(app)
    assert client.post("/api/v1/forecasts/run").json()["records"] == 1
    assert client.post("/api/v1/recommendations/run").json()["status"] == "OPTIMAL"
    assert client.post("/api/v1/scenarios/demand_up/run").json()["records"] == 1
    app.dependency_overrides.clear()
