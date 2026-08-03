"""Point-in-time inventory feature calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_inventory_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add inventory signals using only same-day opening state and earlier demand."""
    result = frame.copy()
    result["current_stock"] = result["current_stock"].fillna(0)
    demand_rate = result["rolling_mean_7"].fillna(result["lag_7"]).replace(0, np.nan)
    result["days_of_supply"] = (result["current_stock"] / demand_rate).fillna(999.0)
    result["open_purchase_order_quantity"] = result["open_purchase_order_quantity"].fillna(0)
    result["expected_inbound_quantity"] = result["expected_inbound_quantity"].fillna(0)
    result["supplier_lead_time"] = result["supplier_lead_time"].fillna(7)
    variability = result["rolling_std_7"].fillna(0)
    result["safety_stock"] = 1.645 * variability * np.sqrt(result["supplier_lead_time"])
    result["reorder_point"] = (
        demand_rate.fillna(0) * result["supplier_lead_time"] + result["safety_stock"]
    )
    result["stockout_flag"] = (result["current_stock"] <= result["reorder_point"]).astype(int)
    return result
