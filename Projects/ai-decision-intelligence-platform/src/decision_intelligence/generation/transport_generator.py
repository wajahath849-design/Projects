"""Supplier-to-warehouse transportation lane generation."""

from __future__ import annotations

import random

import pandas as pd


def generate_transport_lanes(
    rng: random.Random,
    suppliers: pd.DataFrame,
    warehouses: pd.DataFrame,
) -> pd.DataFrame:
    """Generate a connected lane network with one preferred lane per supplier."""
    rows: list[dict[str, object]] = []
    warehouse_records = warehouses.to_dict("records")
    for supplier_index, supplier in enumerate(suppliers.to_dict("records")):
        preferred = supplier_index % len(warehouse_records)
        for warehouse_index, warehouse in enumerate(warehouse_records):
            distance = rng.randint(80, 3200)
            rows.append(
                {
                    "supplier_id": supplier["supplier_id"],
                    "warehouse_id": warehouse["warehouse_id"],
                    "distance_km": distance,
                    "base_shipping_cost": round(75 + distance * rng.uniform(0.08, 0.16), 4),
                    "shipping_cost_per_unit": round(0.02 + distance * 0.00008, 6),
                    "average_transit_days": round(
                        max(1.0, distance / 650 + rng.uniform(0, 1.5)), 4
                    ),
                    "transit_variability": round(rng.uniform(0.25, 2.0), 4),
                    "carbon_emission_per_unit": round(distance * 0.00012, 6),
                    "preferred_lane_flag": warehouse_index == preferred,
                }
            )
    return pd.DataFrame(rows)
