"""Deterministic warehouse and business-constraint generation."""

from __future__ import annotations

import random

import pandas as pd


def generate_warehouses(
    rng: random.Random,
    state_ids: list[str],
    count: int = 5,
) -> pd.DataFrame:
    """Generate capacity-valid warehouses distributed across available states."""
    if not 5 <= count <= 10:
        raise ValueError("Warehouse count must be between 5 and 10")
    if not state_ids:
        raise ValueError("At least one state is required")
    rows: list[dict[str, object]] = []
    for index in range(1, count + 1):
        rows.append(
            {
                "warehouse_id": f"SYN_WH_{index:02d}",
                "warehouse_name": f"Synthetic Distribution Center {index:02d}",
                "state_id": state_ids[(index - 1) % len(state_ids)],
                "capacity_units": rng.randint(25_000, 75_000),
                "current_utilization": round(rng.uniform(0.30, 0.72), 6),
                "holding_cost_per_unit_day": round(rng.uniform(0.002, 0.012), 6),
                "handling_cost_per_unit": round(rng.uniform(0.05, 0.35), 4),
                "service_level_target": round(rng.uniform(0.92, 0.99), 6),
                "active_flag": True,
            }
        )
    return pd.DataFrame(rows)


def generate_constraints(
    warehouses: pd.DataFrame,
    effective_date_key: int,
) -> pd.DataFrame:
    """Generate global budget and warehouse capacity constraints."""
    rows: list[dict[str, object]] = [
        {
            "constraint_id": "SYN_GLOBAL_PURCHASING_BUDGET",
            "constraint_type": "BUDGET",
            "scope_type": "GLOBAL",
            "scope_id": None,
            "parameter_name": "available_purchasing_budget",
            "parameter_value": 250000.0,
            "unit_of_measure": "USD",
            "effective_date_key": effective_date_key,
            "expiration_date_key": None,
            "active_flag": True,
        }
    ]
    for warehouse in warehouses.to_dict("records"):
        rows.append(
            {
                "constraint_id": f"SYN_CAPACITY_{warehouse['warehouse_id']}",
                "constraint_type": "CAPACITY",
                "scope_type": "WAREHOUSE",
                "scope_id": warehouse["warehouse_id"],
                "parameter_name": "capacity_units",
                "parameter_value": float(warehouse["capacity_units"]),
                "unit_of_measure": "units",
                "effective_date_key": effective_date_key,
                "expiration_date_key": None,
                "active_flag": True,
            }
        )
    return pd.DataFrame(rows)
