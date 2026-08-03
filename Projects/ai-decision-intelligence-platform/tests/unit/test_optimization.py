"""Small OR-Tools sample and independent constraint-validation tests."""

from __future__ import annotations

import pandas as pd

from decision_intelligence.optimization.optimizer import (
    solve_replenishment,
    validate_solution,
)


def _candidate_frame() -> pd.DataFrame:
    common = {
        "product_key": 1, "warehouse_key": 1, "product_id": "P1",
        "warehouse_id": "W1", "minimum_order_quantity": 10.0,
        "maximum_order_quantity": 100.0, "daily_capacity": 100.0,
        "supplier_daily_capacity": 100.0, "lead_time_days": 2.0,
        "delay_probability": 0.05, "base_shipping_cost": 5.0,
        "shipping_cost_per_unit": 0.2, "average_transit_days": 1.0,
        "holding_cost_per_unit_day": 0.01, "warehouse_available_capacity": 100.0,
    }
    return pd.DataFrame([
        {**common, "supplier_key": 1, "supplier_id": "S1", "purchase_cost": 2.0},
        {**common, "supplier_key": 2, "supplier_id": "S2", "purchase_cost": 3.0},
    ])


def test_small_optimization_is_optimal_and_valid() -> None:
    candidates = _candidate_frame()
    requirements = pd.DataFrame([
        {"product_key": 1, "warehouse_key": 1, "required_quantity": 15.0}
    ])
    solution = solve_replenishment(
        candidates, requirements, 1000, 30, 10,
        {"stockout": 25.0, "late": 2.0, "excess": 0.25},
    )
    assert solution.status == "OPTIMAL"
    assert not solution.diagnostics
    assert solution.orders["recommended_order_quantity"].sum() >= 15
    assert solution.orders["recommended_order_quantity"].map(float.is_integer).all()


def test_validator_rejects_constraint_violation() -> None:
    candidates = _candidate_frame()
    requirements = pd.DataFrame([
        {"product_key": 1, "warehouse_key": 1, "required_quantity": 15.0}
    ])
    invalid = candidates.iloc[[0]].copy()
    invalid["recommended_order_quantity"] = 5.0
    failures = validate_solution(candidates, requirements, invalid, 1000, 30)
    assert any("MOQ" in failure for failure in failures)
    assert any("Demand coverage" in failure for failure in failures)
