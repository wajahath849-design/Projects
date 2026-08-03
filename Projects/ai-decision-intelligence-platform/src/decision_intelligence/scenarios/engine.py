"""Deterministic scenario adjustments over a preserved operational baseline."""

from __future__ import annotations

from typing import Any

SUPPORTED_SCENARIOS = frozenset({
    "PRICE_CHANGE", "DEMAND_CHANGE", "SUPPLIER_DELAY", "SUPPLIER_CAPACITY",
    "WAREHOUSE_CAPACITY", "BUDGET_CHANGE", "TRANSPORT_COST", "SERVICE_LEVEL",
    "PROMOTION_UPLIFT", "STOCK_LOSS",
})


def _ratio(baseline_value: float, scenario_value: float) -> float:
    return scenario_value / baseline_value if baseline_value else 1.0 + scenario_value


def apply_scenario(
    baseline: dict[str, Any],
    scenario_type: str,
    baseline_value: float,
    scenario_value: float,
) -> dict[str, float]:
    """Apply one supported scenario without mutating the baseline record."""
    if scenario_type not in SUPPORTED_SCENARIOS:
        raise ValueError(f"Unsupported scenario type: {scenario_type}")
    demand = float(baseline["baseline_demand"])
    price = float(baseline["average_price"])
    inventory = float(baseline["baseline_inventory"])
    probability = float(baseline["baseline_stockout_probability"])
    order = float(baseline["baseline_order_quantity"])
    purchase = float(baseline["baseline_purchase_cost"])
    transportation = float(baseline["baseline_transportation_cost"])
    holding = float(baseline["baseline_holding_cost"])
    protected = float(baseline["baseline_revenue_protected"])
    ratio = _ratio(baseline_value, scenario_value)
    if scenario_type == "PRICE_CHANGE":
        price *= ratio
        demand *= max(0.0, 1.0 - 0.8 * (ratio - 1.0))
    elif scenario_type == "DEMAND_CHANGE":
        demand *= ratio
        order *= ratio
        purchase *= ratio
        holding *= ratio
        probability = min(1.0, probability + max(ratio - 1.0, 0.0) * 0.5)
    elif scenario_type == "SUPPLIER_DELAY":
        delay = scenario_value - baseline_value
        order += max(delay, 0.0) * demand / 30.0
        holding += max(delay, 0.0) * max(order, 0.0) * 0.01
        probability = min(1.0, probability + max(delay, 0.0) * 0.03)
    elif scenario_type in {"SUPPLIER_CAPACITY", "WAREHOUSE_CAPACITY"}:
        order *= max(ratio, 0.0)
        purchase *= max(ratio, 0.0)
        transportation *= max(ratio, 0.0)
        holding *= max(ratio, 0.0)
        probability = min(1.0, probability + max(1.0 - ratio, 0.0) * 0.6)
    elif scenario_type == "BUDGET_CHANGE":
        order *= max(ratio, 0.0)
        purchase *= max(ratio, 0.0)
        transportation *= max(ratio, 0.0)
        holding *= max(ratio, 0.0)
        probability = min(1.0, probability + max(1.0 - ratio, 0.0) * 0.5)
    elif scenario_type == "TRANSPORT_COST":
        transportation *= max(ratio, 0.0)
    elif scenario_type == "SERVICE_LEVEL":
        order *= max(ratio, 0.0)
        purchase *= max(ratio, 0.0)
        holding *= max(ratio, 0.0)
        probability = max(0.0, probability - max(ratio - 1.0, 0.0) * 0.5)
    elif scenario_type == "PROMOTION_UPLIFT":
        demand *= ratio
        price *= 0.95
        order *= ratio
        purchase *= ratio
        holding *= ratio
        probability = min(1.0, probability + max(ratio - 1.0, 0.0) * 0.4)
    elif scenario_type == "STOCK_LOSS":
        loss = max(scenario_value - baseline_value, 0.0)
        inventory = max(0.0, inventory - loss)
        order += loss
        purchase += loss * float(baseline.get("average_purchase_cost", 0.0))
        probability = min(1.0, probability + loss / max(inventory + loss, 1.0))
    scenario_revenue = demand * price
    order_ratio = order / max(float(baseline["baseline_order_quantity"]), 1.0)
    scenario_protected = protected * max(order_ratio, 0.0)
    baseline_components = (
        float(baseline["baseline_purchase_cost"])
        + float(baseline["baseline_transportation_cost"])
        + float(baseline["baseline_holding_cost"])
    )
    other_cost = max(float(baseline["baseline_total_cost"]) - baseline_components, 0.0)
    total_cost = purchase + transportation + holding + other_cost
    return {
        "scenario_demand": max(demand, 0.0),
        "scenario_revenue": max(scenario_revenue, 0.0),
        "scenario_inventory": inventory,
        "scenario_stockout_probability": min(max(probability, 0.0), 1.0),
        "scenario_order_quantity": max(order, 0.0),
        "scenario_purchase_cost": max(purchase, 0.0),
        "scenario_transportation_cost": max(transportation, 0.0),
        "scenario_holding_cost": max(holding, 0.0),
        "scenario_total_cost": max(total_cost, 0.0),
        "scenario_profit": scenario_revenue - total_cost,
        "scenario_revenue_protected": max(scenario_protected, 0.0),
    }
