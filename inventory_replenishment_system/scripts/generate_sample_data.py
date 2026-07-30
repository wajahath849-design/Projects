from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parents[1] / "sample_data"


def main() -> None:
    rng = np.random.default_rng(42)
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=239)
    warehouses = ["WH-HAM", "WH-MUC"]
    skus = {
        "ELEC-1001": {"base": 18, "trend": 0.025, "cost": 42.50},
        "ELEC-1002": {"base": 10, "trend": 0.015, "cost": 88.00},
        "MECH-2001": {"base": 32, "trend": -0.005, "cost": 7.25},
    }

    transaction_rows = []
    snapshot_rows = []
    transaction_number = 1
    dates = pd.date_range(start_date, end_date, freq="D")
    latest_on_hand: dict[tuple[str, str], float] = {}

    for warehouse_index, warehouse in enumerate(warehouses):
        for sku_index, (sku, params) in enumerate(skus.items()):
            on_hand = 850.0 - warehouse_index * 80 - sku_index * 120
            for day_index, ts in enumerate(dates):
                weekday_factor = 0.75 if ts.dayofweek >= 5 else 1.0
                annual_factor = 1 + 0.15 * np.sin(2 * np.pi * ts.dayofyear / 365.25)
                promo_factor = 1.45 if day_index in range(150, 165) and sku.startswith("ELEC") else 1.0
                mean = max(0.1, (params["base"] + params["trend"] * day_index) * weekday_factor * annual_factor * promo_factor)
                quantity = int(rng.poisson(mean))
                transaction_rows.append(
                    {
                        "source_transaction_id": f"TX-{transaction_number:08d}",
                        "transaction_ts": datetime.combine(ts.date(), datetime.min.time(), tzinfo=timezone.utc).isoformat(),
                        "warehouse_code": warehouse,
                        "sku_code": sku,
                        "transaction_type": "SALE",
                        "quantity": quantity,
                        "unit_cost": params["cost"],
                        "source_system": "DEMO",
                    }
                )
                transaction_number += 1
                on_hand -= quantity
                if on_hand < 250:
                    receipt = 700 if sku.startswith("ELEC") else 1200
                    on_hand += receipt
                    transaction_rows.append(
                        {
                            "source_transaction_id": f"TX-{transaction_number:08d}",
                            "transaction_ts": datetime.combine(ts.date(), datetime.min.time(), tzinfo=timezone.utc).replace(hour=12).isoformat(),
                            "warehouse_code": warehouse,
                            "sku_code": sku,
                            "transaction_type": "RECEIPT",
                            "quantity": receipt,
                            "unit_cost": params["cost"] * 0.85,
                            "source_system": "DEMO",
                        }
                    )
                    transaction_number += 1
            latest_on_hand[(warehouse, sku)] = max(0.0, on_hand)

    snapshot_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for (warehouse, sku), on_hand in latest_on_hand.items():
        snapshot_rows.append(
            {
                "snapshot_ts": snapshot_ts,
                "warehouse_code": warehouse,
                "sku_code": sku,
                "on_hand_qty": round(on_hand, 2),
                "allocated_qty": int(rng.integers(10, 60)),
                "on_order_qty": int(rng.choice([0, 0, 100, 200])),
                "backorder_qty": int(rng.choice([0, 0, 0, 20])),
                "source_system": "DEMO",
            }
        )

    lead_rows = []
    for order_no in range(1, 81):
        sku = list(skus)[order_no % len(skus)]
        supplier = "SUP-002" if sku == "MECH-2001" else "SUP-001"
        warehouse = warehouses[order_no % len(warehouses)]
        order_date = start_date + timedelta(days=order_no * 2)
        contractual = 12 if supplier == "SUP-002" else 8
        actual = max(2, int(round(rng.normal(contractual + 1.2, 2.4))))
        receipt_date = order_date + timedelta(days=actual)
        lead_rows.append(
            {
                "supplier_code": supplier,
                "warehouse_code": warehouse,
                "sku_code": sku,
                "purchase_order_no": f"DEMO-PO-{order_no:05d}",
                "order_date": order_date.isoformat(),
                "promised_date": (order_date + timedelta(days=contractual)).isoformat(),
                "receipt_date": receipt_date.isoformat(),
                "delay_reason": "Carrier delay" if actual > contractual + 2 else "",
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(transaction_rows).to_csv(OUTPUT_DIR / "transactions.csv", index=False)
    pd.DataFrame(snapshot_rows).to_csv(OUTPUT_DIR / "snapshots.csv", index=False)
    pd.DataFrame(lead_rows).to_csv(OUTPUT_DIR / "lead_times.csv", index=False)
    print(f"Sample data generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
