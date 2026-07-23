from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from statistics import NormalDist
from typing import Iterable


@dataclass(frozen=True)
class ReplenishmentInputs:
    service_level: float
    avg_daily_demand: float
    demand_stddev: float
    avg_lead_time_days: float
    lead_time_stddev: float
    inventory_position: float
    minimum_order_qty: float = 1.0
    order_multiple: float = 1.0
    review_period_days: float = 7.0


@dataclass(frozen=True)
class ReplenishmentResult:
    z_value: float
    safety_stock: float
    reorder_point: float
    target_stock: float
    recommended_order_qty: float
    expected_stockout_date: date | None
    risk_band: str
    details: dict[str, float | str | None]


def _validate(inputs: ReplenishmentInputs) -> None:
    if not 0.5 < inputs.service_level < 0.9999:
        raise ValueError("service_level must be between 0.5 and 0.9999")
    for field_name in (
        "avg_daily_demand",
        "demand_stddev",
        "avg_lead_time_days",
        "lead_time_stddev",
        "minimum_order_qty",
        "order_multiple",
        "review_period_days",
    ):
        value = getattr(inputs, field_name)
        if value < 0:
            raise ValueError(f"{field_name} cannot be negative")
    if inputs.minimum_order_qty <= 0 or inputs.order_multiple <= 0:
        raise ValueError("minimum_order_qty and order_multiple must be greater than zero")


def calculate_safety_stock(inputs: ReplenishmentInputs) -> tuple[float, float]:
    """Return (z, safety_stock) for variable demand and variable lead time.

    Assumption: daily demand and lead time are independent. The formula is:
    SS = Z * sqrt(L_bar * sigma_D^2 + D_bar^2 * sigma_L^2)
    """
    _validate(inputs)
    z_value = NormalDist().inv_cdf(inputs.service_level)
    variance_during_lead_time = (
        inputs.avg_lead_time_days * inputs.demand_stddev**2
        + inputs.avg_daily_demand**2 * inputs.lead_time_stddev**2
    )
    safety_stock = z_value * math.sqrt(max(0.0, variance_during_lead_time))
    return z_value, safety_stock


def round_order_quantity(quantity: float, minimum_order_qty: float, order_multiple: float) -> float:
    if quantity <= 0:
        return 0.0
    quantity = max(quantity, minimum_order_qty)
    return math.ceil(quantity / order_multiple) * order_multiple


def estimate_stockout_date(
    inventory_position: float,
    future_daily_forecast: Iterable[tuple[date, float]],
) -> date | None:
    remaining = inventory_position
    for forecast_date, forecast_qty in sorted(future_daily_forecast, key=lambda item: item[0]):
        remaining -= max(0.0, float(forecast_qty))
        if remaining <= 0:
            return forecast_date
    return None


def classify_risk(
    expected_stockout_date: date | None,
    avg_lead_time_days: float,
    as_of_date: date,
) -> str:
    if expected_stockout_date is None:
        return "LOW"
    days_until_stockout = (expected_stockout_date - as_of_date).days
    if days_until_stockout <= max(1, math.ceil(avg_lead_time_days)):
        return "CRITICAL"
    if days_until_stockout <= math.ceil(avg_lead_time_days + 7):
        return "HIGH"
    if days_until_stockout <= math.ceil(avg_lead_time_days + 21):
        return "MEDIUM"
    return "LOW"


def calculate_replenishment(
    inputs: ReplenishmentInputs,
    future_daily_forecast: Iterable[tuple[date, float]],
    as_of_date: date | None = None,
) -> ReplenishmentResult:
    _validate(inputs)
    as_of_date = as_of_date or date.today()
    forecast = [(d, max(0.0, float(q))) for d, q in future_daily_forecast]

    z_value, safety_stock = calculate_safety_stock(inputs)
    expected_lead_time_demand = inputs.avg_daily_demand * inputs.avg_lead_time_days
    reorder_point = expected_lead_time_demand + safety_stock
    target_stock = (
        inputs.avg_daily_demand * (inputs.avg_lead_time_days + inputs.review_period_days)
        + safety_stock
    )
    raw_order_qty = max(0.0, target_stock - inputs.inventory_position)
    recommended_order_qty = round_order_quantity(
        raw_order_qty,
        inputs.minimum_order_qty,
        inputs.order_multiple,
    )
    expected_stockout_date = estimate_stockout_date(inputs.inventory_position, forecast)
    risk_band = classify_risk(expected_stockout_date, inputs.avg_lead_time_days, as_of_date)

    details = {
        **asdict(inputs),
        "expected_lead_time_demand": expected_lead_time_demand,
        "raw_order_qty": raw_order_qty,
        "as_of_date": as_of_date.isoformat(),
        "forecast_end_date": max((d for d, _ in forecast), default=as_of_date).isoformat(),
    }

    return ReplenishmentResult(
        z_value=z_value,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        target_stock=target_stock,
        recommended_order_qty=recommended_order_qty,
        expected_stockout_date=expected_stockout_date,
        risk_band=risk_band,
        details=details,
    )
