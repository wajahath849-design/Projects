"""Strictly shifted demand lag and rolling-window features."""

from __future__ import annotations

import pandas as pd

LAGS = (1, 7, 14, 28, 56)
ROLLING_WINDOWS = (7, 14, 28)


def add_lag_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Build lags and rolling statistics using values before the current date only."""
    result = frame.sort_values(["product_id", "store_id", "date"]).copy()
    groups = result.groupby(["product_id", "store_id"], sort=False)["target"]
    for lag in LAGS:
        result[f"lag_{lag}"] = groups.shift(lag)
    shifted = groups.shift(1)
    for window in ROLLING_WINDOWS:
        rolling = shifted.groupby(
            [result["product_id"], result["store_id"]], sort=False
        ).rolling(window, min_periods=window)
        result[f"rolling_mean_{window}"] = rolling.mean().reset_index(level=[0, 1], drop=True)
    for window in (7, 28):
        rolling = shifted.groupby(
            [result["product_id"], result["store_id"]], sort=False
        ).rolling(window, min_periods=window)
        result[f"rolling_std_{window}"] = rolling.std(ddof=0).reset_index(level=[0, 1], drop=True)
    rolling_28 = shifted.groupby(
        [result["product_id"], result["store_id"]], sort=False
    ).rolling(28, min_periods=28)
    result["rolling_min_28"] = rolling_28.min().reset_index(level=[0, 1], drop=True)
    result["rolling_max_28"] = rolling_28.max().reset_index(level=[0, 1], drop=True)
    return result
