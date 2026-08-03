"""Weekly seasonal-naive demand benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd

from decision_intelligence.forecasting.base_model import ForecastModel


class SeasonalNaiveModel(ForecastModel):
    """Predict each observation from its seven-day demand lag."""

    model_id = "SEASONAL_NAIVE"
    model_name = "Seasonal Naive"

    def fit(self, frame: pd.DataFrame, features: list[str]) -> None:
        if frame.empty or "lag_7" not in frame:
            raise ValueError("Seasonal Naive requires nonempty lag_7 data")

    def predict(self, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Return lag seven, using lag one only when the seasonal lag is missing."""
        fallback = frame["lag_1"] if "lag_1" in frame else frame["lag_7"]
        return np.asarray(
            np.clip(frame["lag_7"].fillna(fallback).to_numpy(dtype=float), 0, None),
            dtype=float,
        )

    def parameters(self) -> dict[str, object]:
        return {"seasonal_period": 7}
