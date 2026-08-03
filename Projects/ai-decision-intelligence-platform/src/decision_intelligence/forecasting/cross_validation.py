"""Rolling-origin split utilities that never shuffle time."""

from __future__ import annotations

import pandas as pd


def rolling_origin_splits(
    dates: pd.Series, horizon: int = 7, minimum_train_days: int = 7, max_folds: int = 3
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return expanding train-end and validation-end date pairs."""
    unique = sorted(pd.to_datetime(dates).unique())
    splits: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for train_size in range(minimum_train_days, len(unique) - horizon + 1, horizon):
        splits.append((
            pd.Timestamp(unique[train_size - 1]),
            pd.Timestamp(unique[train_size + horizon - 1]),
        ))
    return splits[-max_folds:]
