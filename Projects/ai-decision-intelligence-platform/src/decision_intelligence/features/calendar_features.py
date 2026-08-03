"""Calendar feature transformations available at prediction time."""

from __future__ import annotations

import pandas as pd


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add deterministic date and event features without using the target."""
    result = frame.copy()
    dates = pd.to_datetime(result["date"])
    result["day_of_week"] = dates.dt.dayofweek
    result["day_of_month"] = dates.dt.day
    result["week_of_year"] = dates.dt.isocalendar().week.astype(int)
    result["month"] = dates.dt.month
    result["quarter"] = dates.dt.quarter
    result["year"] = dates.dt.year
    result["weekend_flag"] = (dates.dt.dayofweek >= 5).astype(int)
    result["event_flag"] = result["event_name"].notna().astype(int)
    result["event_type_code"] = pd.Categorical(result["event_type"]).codes
    result["snap_flag"] = result[["snap_ca", "snap_tx", "snap_wi"]].max(axis=1).astype(int)
    return result
