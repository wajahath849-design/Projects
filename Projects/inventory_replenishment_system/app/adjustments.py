from __future__ import annotations

from datetime import date
from typing import Any


def apply_adjustments(
    base: dict[str, Any],
    demand: dict[str, float],
    forecasts: list[tuple[date, float]],
    overrides: list[dict[str, Any]],
    external_adjustment: dict[str, float | str] | None = None,
) -> tuple[dict[str, Any], dict[str, float], list[tuple[date, float]], dict[str, Any]]:
    """Combine external regional modifiers and approved human overrides."""
    base = dict(base)
    demand = dict(demand)
    adjusted_forecasts = list(forecasts)
    controls: dict[str, Any] = {
        "safety_stock_override": None,
        "reorder_qty_override": None,
        "hold_replenishment": False,
        "applied_override_ids": [],
    }
    external_adjustment = external_adjustment or {}
    demand_multiplier = max(0.0, float(external_adjustment.get("demand_multiplier", 1.0)))
    lead_time_penalty = max(0.0, float(external_adjustment.get("lead_time_penalty", 0.0)))
    controls["external_adjustment"] = external_adjustment

    for override in overrides:
        controls["applied_override_ids"].append(int(override["override_id"]))
        override_type = override["override_type"]
        numeric = float(override["numeric_value"]) if override["numeric_value"] is not None else None
        if override_type == "PHYSICAL_COUNT" and numeric is not None:
            base["on_hand_qty"] = numeric
            base["inventory_position_qty"] = (
                numeric + float(base["on_order_qty"]) - float(base["allocated_qty"]) - float(base["backorder_qty"])
            )
        elif override_type == "DEMAND_MULTIPLIER" and numeric is not None:
            demand_multiplier *= numeric
        elif override_type == "LEAD_TIME_PENALTY" and numeric is not None:
            lead_time_penalty += numeric
        elif override_type == "SAFETY_STOCK" and numeric is not None:
            controls["safety_stock_override"] = numeric
        elif override_type == "REORDER_QTY" and numeric is not None:
            controls["reorder_qty_override"] = numeric
        elif override_type == "HOLD_REPLENISHMENT":
            controls["hold_replenishment"] = True

    demand["avg_daily_demand"] *= demand_multiplier
    demand["demand_stddev"] *= demand_multiplier
    adjusted_forecasts = [(forecast_date, quantity * demand_multiplier) for forecast_date, quantity in adjusted_forecasts]
    controls["demand_multiplier"] = demand_multiplier
    controls["lead_time_penalty"] = lead_time_penalty
    return base, demand, adjusted_forecasts, controls
