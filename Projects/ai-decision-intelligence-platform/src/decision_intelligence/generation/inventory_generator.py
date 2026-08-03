"""Logically reconciled daily warehouse inventory generation."""

from __future__ import annotations

import math

import pandas as pd


def generate_inventory(
    products: pd.DataFrame,
    warehouses: pd.DataFrame,
    sales: pd.DataFrame,
    purchase_orders: pd.DataFrame,
    purchase_order_lines: pd.DataFrame,
    date_keys: list[int],
) -> pd.DataFrame:
    """Generate stock flows tied to demand and actual purchase-order receipts."""
    warehouse_ids = list(warehouses["warehouse_id"].astype(str))
    product_ids = list(products["product_id"].astype(str))
    receipt_source = purchase_order_lines.merge(
        purchase_orders[["purchase_order_id", "warehouse_id", "actual_delivery_date_key"]],
        on="purchase_order_id",
        how="inner",
        validate="one_to_one",
    ).dropna(subset=["actual_delivery_date_key"])
    receipts = {
        (
            str(row.product_id),
            str(row.warehouse_id),
            int(float(str(row.actual_delivery_date_key))),
        ): int(float(str(row.received_quantity)))
        for row in receipt_source.itertuples(index=False)
        if int(float(str(row.received_quantity))) > 0
    }
    demand_lookup = {
        (str(row.product_id), int(str(row.date_key))): int(str(row.demand))
        for row in sales.itertuples(index=False)
    }
    average_demand = sales.groupby("product_id")["demand"].mean().to_dict()
    rows: list[dict[str, object]] = []
    closing: dict[tuple[str, str], int] = {}
    for product_index, product_id in enumerate(product_ids):
        initial = max(
            10, math.ceil(float(average_demand.get(product_id, 1.0)) * 8 / len(warehouse_ids))
        )
        for warehouse_id in warehouse_ids:
            closing[(product_id, warehouse_id)] = initial
        for day_index, date_key in enumerate(date_keys):
            total_demand = demand_lookup.get((product_id, date_key), 0)
            base, remainder = divmod(total_demand, len(warehouse_ids))
            for warehouse_index, warehouse_id in enumerate(warehouse_ids):
                opening = closing[(product_id, warehouse_id)]
                received = receipts.get((product_id, warehouse_id, date_key), 0)
                requested = base + int(warehouse_index < remainder)
                available = opening + received
                damaged = int(
                    available > 2 and (product_index + warehouse_index + day_index) % 31 == 0
                )
                reserved = int(
                    available - damaged > requested
                    and (product_index * 3 + warehouse_index + day_index) % 17 == 0
                )
                sellable = max(0, available - damaged - reserved)
                sold = min(requested, sellable)
                lost_sales = requested - sold
                close = opening + received - sold - damaged - reserved
                if close < 0:
                    raise RuntimeError("Inventory generation produced negative closing stock")
                rows.append(
                    {
                        "date_key": date_key,
                        "product_id": product_id,
                        "warehouse_id": warehouse_id,
                        "opening_stock": opening,
                        "received_quantity": received,
                        "sold_quantity": sold,
                        "damaged_quantity": damaged,
                        "reserved_quantity_adjustment": reserved,
                        "closing_stock": close,
                        "lost_sales_quantity": lost_sales,
                        "inventory_value": round(close * (2.0 + product_index * 0.75), 4),
                    }
                )
                closing[(product_id, warehouse_id)] = close
    return pd.DataFrame(rows)
