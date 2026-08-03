"""Auditable inventory calculations with safe edge-case handling."""

from __future__ import annotations

import math
from statistics import NormalDist


def safety_stock(
    daily_demand_std: float,
    lead_time_days: float,
    service_level: float,
) -> float:
    """Return service-level safety stock for independent daily demand."""
    if daily_demand_std < 0 or lead_time_days < 0:
        raise ValueError("Demand variability and lead time must be non-negative")
    if not 0.5 <= service_level < 1:
        raise ValueError("Service level must be at least 0.5 and below 1")
    return NormalDist().inv_cdf(service_level) * daily_demand_std * math.sqrt(lead_time_days)


def reorder_point(mean_daily_demand: float, lead_time_days: float, stock: float) -> float:
    """Return expected lead-time demand plus safety stock."""
    if min(mean_daily_demand, lead_time_days, stock) < 0:
        raise ValueError("Reorder-point inputs must be non-negative")
    return mean_daily_demand * lead_time_days + stock


def days_of_supply(inventory: float, mean_daily_demand: float, zero_value: float = 999.0) -> float:
    """Return safe days of supply, including a configured zero-demand sentinel."""
    if inventory < 0 or mean_daily_demand < 0:
        raise ValueError("Inventory and demand must be non-negative")
    return inventory / mean_daily_demand if mean_daily_demand > 0 else zero_value


def projected_inventory(inventory: float, inbound: float, horizon_demand: float) -> float:
    """Project inventory after known inbound and expected horizon demand."""
    return inventory + inbound - horizon_demand


def stockout_probability(
    available_inventory: float,
    mean_daily_demand: float,
    daily_demand_std: float,
    horizon_days: float,
) -> float:
    """Calculate P(cumulative demand > available inventory) with a normal approximation."""
    if min(available_inventory, mean_daily_demand, daily_demand_std, horizon_days) < 0:
        raise ValueError("Stockout inputs must be non-negative")
    mean = mean_daily_demand * horizon_days
    standard_deviation = daily_demand_std * math.sqrt(horizon_days)
    if standard_deviation == 0:
        return float(mean > available_inventory)
    probability = 1 - NormalDist(mean, standard_deviation).cdf(available_inventory)
    return min(max(probability, 0.0), 1.0)


def classify_inventory(
    inventory: float,
    mean_daily_demand: float,
    reorder: float,
    supply_days: float,
    probability: float,
    thresholds: dict[str, float],
) -> str:
    """Classify inventory using ordered, configurable operational thresholds."""
    if inventory <= 0 or probability >= thresholds["critical_probability"]:
        return "Critical"
    if mean_daily_demand <= thresholds["obsolete_daily_demand"] and inventory > 0:
        return "Obsolete Risk"
    if probability >= thresholds["at_risk_probability"] or inventory < reorder:
        return "At Risk"
    if supply_days >= thresholds["excess_days_supply"]:
        return "Excess"
    return "Healthy"
