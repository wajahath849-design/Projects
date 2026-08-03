"""Cross-table integrity checks for generated enterprise operations."""

from __future__ import annotations

from dataclasses import dataclass

from decision_intelligence.generation.enterprise_generator import EnterpriseData


@dataclass(frozen=True)
class GenerationValidation:
    """Named generated-data checks and any critical failures."""

    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


def validate_enterprise_data(data: EnterpriseData) -> GenerationValidation:
    """Validate referential, capacity, reconciliation, and lifecycle invariants."""
    checks: list[str] = []
    failures: list[str] = []
    supplier_ids = set(data.suppliers["supplier_id"])
    warehouse_ids = set(data.warehouses["warehouse_id"])
    relationship_suppliers = set(data.supplier_products["supplier_id"])
    lane_suppliers = set(data.transportation_lanes["supplier_id"])
    lane_warehouses = set(data.transportation_lanes["warehouse_id"])
    if relationship_suppliers <= supplier_ids and lane_suppliers <= supplier_ids:
        checks.append("supplier_referential_integrity=passed")
    else:
        failures.append("Supplier references contain unknown identifiers")
    if (
        lane_warehouses <= warehouse_ids
        and set(data.inventory_snapshots["warehouse_id"]) <= warehouse_ids
    ):
        checks.append("warehouse_referential_integrity=passed")
    else:
        failures.append("Warehouse references contain unknown identifiers")
    supplier_capacity_valid = (
        data.suppliers["daily_capacity"] >= data.suppliers["minimum_order_quantity"]
    ).all()
    relationship_capacity_valid = (
        data.supplier_products["daily_capacity"] >= data.supplier_products["minimum_order_quantity"]
    ).all()
    if bool(supplier_capacity_valid and relationship_capacity_valid):
        checks.append("supplier_capacity_validity=passed")
    else:
        failures.append("A supplier capacity is below its minimum order quantity")
    inventory = data.inventory_snapshots
    reconciled = (
        inventory["closing_stock"]
        == inventory["opening_stock"]
        + inventory["received_quantity"]
        - inventory["sold_quantity"]
        - inventory["damaged_quantity"]
        - inventory["reserved_quantity_adjustment"]
    ).all()
    if bool(reconciled and (inventory["closing_stock"] >= 0).all()):
        checks.append("inventory_reconciliation=passed")
    else:
        failures.append("Inventory does not reconcile or contains negative closing stock")
    utilization = inventory.groupby(["date_key", "warehouse_id"], as_index=False)[
        "closing_stock"
    ].sum()
    utilization = utilization.merge(
        data.warehouses[["warehouse_id", "capacity_units"]],
        on="warehouse_id",
        validate="many_to_one",
    )
    if bool((utilization["closing_stock"] <= utilization["capacity_units"]).all()):
        checks.append("warehouse_capacity_validity=passed")
    else:
        failures.append("Generated inventory exceeds warehouse capacity")
    lifecycle = data.purchase_order_lines.merge(
        data.purchase_orders[["purchase_order_id", "status", "actual_delivery_date_key"]],
        on="purchase_order_id",
        validate="one_to_one",
    )
    valid_completed = (
        lifecycle.loc[lifecycle["status"] == "COMPLETED", "received_quantity"]
        .eq(lifecycle.loc[lifecycle["status"] == "COMPLETED", "ordered_quantity"])
        .all()
    )
    valid_partial = (
        lifecycle.loc[lifecycle["status"] == "PARTIAL", "received_quantity"] > 0
    ).all() and (
        lifecycle.loc[lifecycle["status"] == "PARTIAL", "received_quantity"]
        < lifecycle.loc[lifecycle["status"] == "PARTIAL", "ordered_quantity"]
    ).all()
    valid_cancelled = (
        lifecycle.loc[lifecycle["status"] == "CANCELLED", "cancelled_quantity"]
        .eq(lifecycle.loc[lifecycle["status"] == "CANCELLED", "ordered_quantity"])
        .all()
    )
    no_unexpected_receipts = (
        lifecycle.loc[
            lifecycle["status"].isin(["OPEN", "DELAYED", "CANCELLED"]), "received_quantity"
        ]
        .eq(0)
        .all()
    )
    if bool(valid_completed and valid_partial and valid_cancelled and no_unexpected_receipts):
        checks.append("purchase_order_lifecycle=passed")
    else:
        failures.append("Purchase-order lifecycle quantities are inconsistent")
    return GenerationValidation(not failures, tuple(checks), tuple(failures))
