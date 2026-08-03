"""Demand-linked purchase order and delivery lifecycle generation."""

from __future__ import annotations

import math
import random

import pandas as pd


def generate_purchase_orders(
    rng: random.Random,
    products: pd.DataFrame,
    warehouses: pd.DataFrame,
    supplier_products: pd.DataFrame,
    lanes: pd.DataFrame,
    date_keys: list[int],
    average_demand: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate feasible orders spanning completed, partial, delayed, cancelled, and open states."""
    if len(date_keys) < 14:
        raise ValueError("Purchase-order generation requires at least 14 dates")
    statuses = ("COMPLETED", "PARTIAL", "DELAYED", "CANCELLED", "OPEN")
    orders: list[dict[str, object]] = []
    lines: list[dict[str, object]] = []
    sequence = 0
    relationships = supplier_products.sort_values(
        ["product_id", "preferred_supplier_flag"], ascending=[True, False]
    )
    for product in products.to_dict("records"):
        choices = relationships[relationships["product_id"] == product["product_id"]]
        if choices.empty:
            raise ValueError(f"No supplier relationships for {product['product_id']}")
        for warehouse in warehouses.to_dict("records"):
            relationship = choices.iloc[sequence % len(choices)].to_dict()
            status = statuses[sequence % len(statuses)]
            order_position = sequence % max(1, len(date_keys) - 10)
            order_date_key = date_keys[order_position]
            lead_time = int(relationship["lead_time_days"])
            expected_position = min(len(date_keys) - 1, order_position + max(1, lead_time))
            if status == "OPEN":
                expected_position = len(date_keys) - 1
            expected_date_key = date_keys[expected_position]
            actual_date_key: int | None = None
            if status in {"COMPLETED", "PARTIAL"}:
                delivery_shift = 0 if status == "COMPLETED" else 1
                actual_position = min(len(date_keys) - 1, expected_position + delivery_shift)
                actual_date_key = date_keys[actual_position]
            minimum = int(relationship["minimum_order_quantity"])
            desired = max(
                minimum, math.ceil(average_demand.get(str(product["product_id"]), 1.0) * 14)
            )
            ordered = min(
                int(relationship["maximum_order_quantity"]),
                int(relationship["daily_capacity"]) * max(1, lead_time),
                math.ceil(desired / minimum) * minimum,
            )
            received = (
                ordered if status == "COMPLETED" else ordered // 2 if status == "PARTIAL" else 0
            )
            cancelled = ordered if status == "CANCELLED" else 0
            supplier_id = str(relationship["supplier_id"])
            warehouse_id = str(warehouse["warehouse_id"])
            lane = lanes[
                (lanes["supplier_id"] == supplier_id) & (lanes["warehouse_id"] == warehouse_id)
            ].iloc[0]
            unit_cost = float(relationship["purchase_cost"])
            transportation_cost = float(lane["base_shipping_cost"]) + ordered * float(
                lane["shipping_cost_per_unit"]
            )
            po_id = f"SYN_PO_{sequence + 1:06d}"
            orders.append(
                {
                    "purchase_order_id": po_id,
                    "supplier_id": supplier_id,
                    "warehouse_id": warehouse_id,
                    "order_date_key": order_date_key,
                    "expected_delivery_date_key": expected_date_key,
                    "actual_delivery_date_key": actual_date_key,
                    "status": status,
                    "total_purchase_cost": round(ordered * unit_cost, 4),
                    "total_transportation_cost": round(transportation_cost, 4),
                }
            )
            lines.append(
                {
                    "purchase_order_id": po_id,
                    "line_number": 1,
                    "product_id": product["product_id"],
                    "ordered_quantity": ordered,
                    "received_quantity": received,
                    "cancelled_quantity": cancelled,
                    "unit_cost": unit_cost,
                }
            )
            sequence += 1
    rng.shuffle(orders)
    return pd.DataFrame(orders), pd.DataFrame(lines)
