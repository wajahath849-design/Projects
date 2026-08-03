"""Unit tests for reproducible and logically valid enterprise generation."""

import pandas as pd

from decision_intelligence.generation.enterprise_generator import EnterpriseGenerator
from decision_intelligence.generation.validation import validate_enterprise_data


def _inputs() -> tuple[pd.DataFrame, list[str], pd.DataFrame, list[int]]:
    products = pd.DataFrame({"product_id": ["P1", "P2"]})
    date_keys = list(range(20260101, 20260115))
    sales = pd.DataFrame(
        [
            {"product_id": product, "date_key": date_key, "demand": 3 + index}
            for index, product in enumerate(products["product_id"])
            for date_key in date_keys
        ]
    )
    return products, ["CA", "TX"], sales, date_keys


def test_generation_is_reproducible_for_same_seed() -> None:
    generator = EnterpriseGenerator(seed=42)
    first = generator.generate(*_inputs())
    second = generator.generate(*_inputs())
    assert first.fingerprints() == second.fingerprints()


def test_generated_operations_pass_all_integrity_rules() -> None:
    data = EnterpriseGenerator(seed=42).generate(*_inputs())
    result = validate_enterprise_data(data)
    assert result.passed, result.failures
    assert len(data.suppliers) == 25
    assert len(data.warehouses) == 5
    assert set(data.purchase_orders["status"]) == {
        "COMPLETED",
        "PARTIAL",
        "DELAYED",
        "CANCELLED",
        "OPEN",
    }


def test_inventory_flow_reconciles_exactly() -> None:
    inventory = EnterpriseGenerator(seed=7).generate(*_inputs()).inventory_snapshots
    expected = (
        inventory["opening_stock"]
        + inventory["received_quantity"]
        - inventory["sold_quantity"]
        - inventory["damaged_quantity"]
        - inventory["reserved_quantity_adjustment"]
    )
    assert expected.equals(inventory["closing_stock"])
    assert (inventory["closing_stock"] >= 0).all()
