"""Leakage-safe historical price features."""

from __future__ import annotations

import numpy as np
import pandas as pd


def add_price_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add shifted prices, category-relative price, and promotion proxy."""
    result = frame.sort_values(["product_id", "store_id", "date"]).copy()
    groups = result.groupby(["product_id", "store_id"], sort=False)["current_price"]
    result["price_lag_7"] = groups.shift(7)
    result["price_lag_28"] = groups.shift(28)
    result["price_change_percentage"] = (
        (result["current_price"] - result["price_lag_7"])
        / result["price_lag_7"].replace(0, np.nan)
    )
    category_average = result.groupby(["category_id", "date"])["current_price"].transform("mean")
    result["relative_price_to_category"] = (
        result["current_price"] / category_average.replace(0, np.nan)
    )
    result["promotion_proxy"] = (
        result["current_price"] < result["price_lag_28"].fillna(result["price_lag_7"])
    ).astype(int)
    return result
