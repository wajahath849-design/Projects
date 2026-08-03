"""Manual examples for every Phase 11 inventory calculation."""

from __future__ import annotations

import math

import pytest

from decision_intelligence.inventory.calculations import (
    classify_inventory,
    days_of_supply,
    projected_inventory,
    reorder_point,
    safety_stock,
    stockout_probability,
)


def test_inventory_calculations_against_manual_examples() -> None:
    buffer = safety_stock(2, 4, 0.95)
    assert buffer == pytest.approx(1.6448536269514722 * 2 * math.sqrt(4))
    assert reorder_point(10, 4, buffer) == pytest.approx(40 + buffer)
    assert days_of_supply(100, 10) == 10
    assert days_of_supply(100, 0) == 999
    assert projected_inventory(100, 20, 150) == -30


def test_stockout_probability_edge_cases() -> None:
    assert stockout_probability(20, 10, 0, 3) == 1
    assert stockout_probability(40, 10, 0, 3) == 0
    assert 0 < stockout_probability(30, 10, 2, 3) < 1


def test_inventory_classification_precedence() -> None:
    thresholds = {
        "critical_probability": 0.8, "at_risk_probability": 0.4,
        "excess_days_supply": 60, "obsolete_daily_demand": 0.05,
    }
    assert classify_inventory(0, 5, 10, 0, 1, thresholds) == "Critical"
    assert classify_inventory(20, 0, 10, 999, 0, thresholds) == "Obsolete Risk"
    assert classify_inventory(5, 5, 10, 1, 0.5, thresholds) == "At Risk"
    assert classify_inventory(500, 5, 10, 100, 0, thresholds) == "Excess"
    assert classify_inventory(50, 5, 10, 10, 0, thresholds) == "Healthy"
