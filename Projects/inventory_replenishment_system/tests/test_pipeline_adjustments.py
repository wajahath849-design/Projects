from datetime import date

import pytest

from app.adjustments import apply_adjustments


def test_external_and_manual_adjustments_are_combined() -> None:
    base = {
        "on_hand_qty": 20.0,
        "on_order_qty": 0.0,
        "allocated_qty": 0.0,
        "backorder_qty": 0.0,
        "inventory_position_qty": 20.0,
        "contractual_lead_time_days": 8.0,
    }
    demand = {"avg_daily_demand": 10.0, "demand_stddev": 2.0}
    forecast = [(date(2026, 7, 24), 10.0)]
    overrides = [
        {"override_id": 1, "override_type": "DEMAND_MULTIPLIER", "numeric_value": 1.2},
        {"override_id": 2, "override_type": "LEAD_TIME_PENALTY", "numeric_value": 2.0},
    ]

    adjusted_base, adjusted_demand, adjusted_forecast, controls = apply_adjustments(
        base,
        demand,
        forecast,
        overrides,
        {"demand_multiplier": 1.5, "lead_time_penalty": 3.0},
    )

    assert adjusted_demand["avg_daily_demand"] == 18.0
    assert adjusted_demand["demand_stddev"] == pytest.approx(3.6)
    assert adjusted_forecast[0][1] == 18.0
    assert controls["lead_time_penalty"] == 5.0
    assert controls["applied_override_ids"] == [1, 2]
    assert adjusted_base["contractual_lead_time_days"] == 8.0
