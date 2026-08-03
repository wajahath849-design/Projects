"""Logical direction and baseline-preservation tests for all scenario types."""

from __future__ import annotations

import pytest

from decision_intelligence.scenarios.engine import SUPPORTED_SCENARIOS, apply_scenario

BASELINE = {
    "baseline_demand": 100.0,
    "average_price": 10.0,
    "baseline_inventory": 80.0,
    "baseline_stockout_probability": 0.2,
    "baseline_order_quantity": 50.0,
    "baseline_purchase_cost": 100.0,
    "baseline_transportation_cost": 20.0,
    "baseline_holding_cost": 10.0,
    "baseline_total_cost": 140.0,
    "baseline_revenue_protected": 300.0,
    "average_purchase_cost": 2.0,
}


@pytest.mark.parametrize("scenario_type", sorted(SUPPORTED_SCENARIOS))
def test_every_scenario_changes_an_expected_output(scenario_type: str) -> None:
    values = {
        "PRICE_CHANGE": (1.0, 1.1), "DEMAND_CHANGE": (1.0, 1.2),
        "SUPPLIER_DELAY": (0.0, 5.0), "SUPPLIER_CAPACITY": (1.0, 0.7),
        "WAREHOUSE_CAPACITY": (1.0, 0.8), "BUDGET_CHANGE": (1.0, 0.8),
        "TRANSPORT_COST": (1.0, 1.25), "SERVICE_LEVEL": (0.95, 0.99),
        "PROMOTION_UPLIFT": (1.0, 1.15), "STOCK_LOSS": (0.0, 20.0),
    }
    before = dict(BASELINE)
    result = apply_scenario(before, scenario_type, *values[scenario_type])
    assert before == BASELINE
    assert any(
        result[key] != BASELINE.get(key.replace("scenario_", "baseline_"))
        for key in result
        if key.replace("scenario_", "baseline_") in BASELINE
    )


def test_demand_and_capacity_directions_are_logical() -> None:
    demand = apply_scenario(BASELINE, "DEMAND_CHANGE", 1.0, 1.2)
    capacity = apply_scenario(BASELINE, "SUPPLIER_CAPACITY", 1.0, 0.7)
    assert demand["scenario_demand"] > BASELINE["baseline_demand"]
    assert demand["scenario_order_quantity"] > BASELINE["baseline_order_quantity"]
    assert capacity["scenario_order_quantity"] < BASELINE["baseline_order_quantity"]
    assert capacity["scenario_stockout_probability"] > BASELINE[
        "baseline_stockout_probability"
    ]
