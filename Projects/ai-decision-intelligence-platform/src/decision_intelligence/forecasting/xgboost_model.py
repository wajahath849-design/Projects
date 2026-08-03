"""Seeded XGBoost demand regressor."""

from __future__ import annotations

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from decision_intelligence.forecasting.base_model import ForecastModel


class XGBoostForecastModel(ForecastModel):
    """XGBoost benchmark with conservative sample-mode parameters."""

    model_id = "XGBOOST"
    model_name = "XGBoost"

    def __init__(self, seed: int = 42) -> None:
        self.model = XGBRegressor(
            n_estimators=120, max_depth=4, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.9, objective="reg:squarederror", random_state=seed,
            n_jobs=1,
        )

    def fit(self, frame: pd.DataFrame, features: list[str]) -> None:
        self.model.fit(frame[features].fillna(0), frame["target"])

    def predict(self, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
        return np.asarray(
            np.clip(self.model.predict(frame[features].fillna(0)), 0, None), dtype=float
        )

    def parameters(self) -> dict[str, object]:
        return self.model.get_params()
