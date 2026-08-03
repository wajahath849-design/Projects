"""Orchestration and reproducibility checks for synthetic enterprise data."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, fields

import pandas as pd

from decision_intelligence.generation.inventory_generator import generate_inventory
from decision_intelligence.generation.purchase_order_generator import generate_purchase_orders
from decision_intelligence.generation.supplier_generator import (
    generate_supplier_products,
    generate_suppliers,
)
from decision_intelligence.generation.transport_generator import generate_transport_lanes
from decision_intelligence.generation.warehouse_generator import (
    generate_constraints,
    generate_warehouses,
)


@dataclass(frozen=True)
class EnterpriseData:
    """All generated operational tables for one deterministic run."""

    suppliers: pd.DataFrame
    warehouses: pd.DataFrame
    supplier_products: pd.DataFrame
    transportation_lanes: pd.DataFrame
    purchase_orders: pd.DataFrame
    purchase_order_lines: pd.DataFrame
    inventory_snapshots: pd.DataFrame
    business_constraints: pd.DataFrame

    def fingerprints(self) -> dict[str, str]:
        """Return stable content hashes for reproducibility verification."""
        result: dict[str, str] = {}
        for field in fields(self):
            frame = getattr(self, field.name)
            canonical = frame.sort_values(list(frame.columns)).reset_index(drop=True)
            payload = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
            result[field.name] = hashlib.sha256(payload).hexdigest()
        return result


class EnterpriseGenerator:
    """Generate connected, demand-driven enterprise operations from sales inputs."""

    def __init__(self, seed: int, supplier_count: int = 25, warehouse_count: int = 5) -> None:
        if seed < 0:
            raise ValueError("Random seed must be non-negative")
        self.seed = seed
        self.supplier_count = supplier_count
        self.warehouse_count = warehouse_count

    def generate(
        self,
        products: pd.DataFrame,
        state_ids: list[str],
        sales: pd.DataFrame,
        date_keys: list[int],
    ) -> EnterpriseData:
        """Generate every connected operational dataset using one seeded RNG."""
        if products.empty or sales.empty or not date_keys:
            raise ValueError("Products, sales, and dates are required")
        rng = random.Random(self.seed)
        suppliers = generate_suppliers(rng, self.supplier_count)
        warehouses = generate_warehouses(rng, state_ids, self.warehouse_count)
        supplier_products = generate_supplier_products(rng, suppliers, products)
        lanes = generate_transport_lanes(rng, suppliers, warehouses)
        average_demand = sales.groupby("product_id")["demand"].mean().to_dict()
        purchase_orders, purchase_order_lines = generate_purchase_orders(
            rng,
            products,
            warehouses,
            supplier_products,
            lanes,
            date_keys,
            {str(key): float(value) for key, value in average_demand.items()},
        )
        inventory = generate_inventory(
            products,
            warehouses,
            sales,
            purchase_orders,
            purchase_order_lines,
            date_keys,
        )
        constraints = generate_constraints(warehouses, min(date_keys))
        return EnterpriseData(
            suppliers=suppliers,
            warehouses=warehouses,
            supplier_products=supplier_products,
            transportation_lanes=lanes,
            purchase_orders=purchase_orders,
            purchase_order_lines=purchase_order_lines,
            inventory_snapshots=inventory,
            business_constraints=constraints,
        )
