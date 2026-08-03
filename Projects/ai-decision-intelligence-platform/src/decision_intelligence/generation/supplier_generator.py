"""Deterministic supplier and supplier-product relationship generation."""

from __future__ import annotations

import random

import pandas as pd


def generate_suppliers(rng: random.Random, count: int = 25) -> pd.DataFrame:
    """Generate suppliers with internally valid reliability and capacity attributes."""
    if not 25 <= count <= 50:
        raise ValueError("Supplier count must be between 25 and 50")
    regions = ("West", "South", "Midwest", "Northeast")
    rows: list[dict[str, object]] = []
    for index in range(1, count + 1):
        minimum = rng.choice((10, 20, 25, 50))
        maximum = minimum * rng.randint(20, 60)
        reliability = round(rng.uniform(0.80, 0.99), 6)
        rows.append(
            {
                "supplier_id": f"SYN_SUP_{index:03d}",
                "supplier_name": f"Synthetic Supplier {index:03d}",
                "supplier_region": regions[(index - 1) % len(regions)],
                "reliability_score": reliability,
                "base_lead_time_days": rng.randint(3, 18),
                "lead_time_variability": round(rng.uniform(0.5, 4.0), 4),
                "delay_probability": round(max(0.01, 1.0 - reliability), 6),
                "minimum_order_quantity": minimum,
                "maximum_order_quantity": maximum,
                "daily_capacity": rng.randint(minimum, maximum),
                "payment_terms_days": rng.choice((15, 30, 45, 60)),
                "risk_level": "LOW"
                if reliability >= 0.93
                else "MEDIUM"
                if reliability >= 0.86
                else "HIGH",
                "active_flag": True,
            }
        )
    return pd.DataFrame(rows)


def generate_supplier_products(
    rng: random.Random,
    suppliers: pd.DataFrame,
    products: pd.DataFrame,
    suppliers_per_product: int = 3,
) -> pd.DataFrame:
    """Assign multiple feasible suppliers to every product."""
    if suppliers_per_product < 2 or suppliers_per_product > len(suppliers):
        raise ValueError("Each product requires at least two available suppliers")
    rows: list[dict[str, object]] = []
    supplier_records = suppliers.to_dict("records")
    for product_index, product in enumerate(products.to_dict("records")):
        start = (product_index * suppliers_per_product) % len(supplier_records)
        selected = [
            supplier_records[(start + offset) % len(supplier_records)]
            for offset in range(suppliers_per_product)
        ]
        base_cost = 2.0 + product_index * 0.75
        for rank, supplier in enumerate(selected):
            minimum = int(supplier["minimum_order_quantity"])
            rows.append(
                {
                    "supplier_id": supplier["supplier_id"],
                    "product_id": product["product_id"],
                    "purchase_cost": round(base_cost * (1 + rng.uniform(-0.08, 0.12)), 4),
                    "minimum_order_quantity": minimum,
                    "maximum_order_quantity": int(supplier["maximum_order_quantity"]),
                    "daily_capacity": max(minimum, int(supplier["daily_capacity"])),
                    "lead_time_days": int(supplier["base_lead_time_days"]),
                    "preferred_supplier_flag": rank == 0,
                    "active_flag": True,
                }
            )
    return pd.DataFrame(rows)
