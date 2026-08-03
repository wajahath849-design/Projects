"""Seeded LightGBM demand regressor."""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from decision_intelligence.forecasting.base_model import ForecastModel


class LightGBMForecastModel(ForecastModel):
    """Primary candidate trained on the same feature set and split as benchmarks."""

    model_id = "LIGHTGBM"
    model_name = "LightGBM"

    def __init__(self, seed: int = 42) -> None:
        self.model = LGBMRegressor(
            n_estimators=120, num_leaves=15, learning_rate=0.05,
            min_child_samples=5, subsample=0.9, colsample_bytree=0.9,
            random_state=seed, n_jobs=1, verbosity=-1,
        )

    def fit(self, frame: pd.DataFrame, features: list[str]) -> None:
        self.model.fit(frame[features].fillna(0), frame["target"])

    def predict(self, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
        return np.asarray(
            np.clip(self.model.predict(frame[features].fillna(0)), 0, None), dtype=float
        )

    def parameters(self) -> dict[str, object]:
        return self.model.get_params()
