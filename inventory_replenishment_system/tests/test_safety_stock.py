from datetime import date, timedelta

import pytest

from app.safety_stock import (
    ReplenishmentInputs,
    calculate_replenishment,
    calculate_safety_stock,
    estimate_stockout_date,
    round_order_quantity,
)


def test_safety_stock_variable_demand_and_lead_time() -> None:
    inputs = ReplenishmentInputs(
        service_level=0.95,
        avg_daily_demand=20,
        demand_stddev=5,
        avg_lead_time_days=8,
        lead_time_stddev=2,
        inventory_position=200,
        minimum_order_qty=20,
        order_multiple=10,
    )
    z_value, safety_stock = calculate_safety_stock(inputs)
    assert z_value == pytest.approx(1.64485, rel=1e-4)
    assert safety_stock == pytest.approx(69.8, rel=0.02)


def test_order_rounding_respects_moq_and_multiple() -> None:
    assert round_order_quantity(0, 20, 10) == 0
    assert round_order_quantity(3, 20, 10) == 20
    assert round_order_quantity(21, 20, 10) == 30


def test_stockout_date() -> None:
    start = date(2026, 1, 1)
    forecast = [(start + timedelta(days=i), 10) for i in range(10)]
    assert estimate_stockout_date(25, forecast) == start + timedelta(days=2)


def test_replenishment_result_is_non_negative_and_rounded() -> None:
    start = date(2026, 1, 1)
    forecast = [(start + timedelta(days=i), 15) for i in range(90)]
    inputs = ReplenishmentInputs(
        service_level=0.95,
        avg_daily_demand=15,
        demand_stddev=4,
        avg_lead_time_days=10,
        lead_time_stddev=1.5,
        inventory_position=80,
        minimum_order_qty=20,
        order_multiple=10,
    )
    result = calculate_replenishment(inputs, forecast, as_of_date=start)
    assert result.safety_stock >= 0
    assert result.reorder_point >= result.safety_stock
    assert result.recommended_order_qty % 10 == 0
    assert result.risk_band == "CRITICAL"
