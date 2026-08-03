"""Shared forecasting model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class ForecastModel(ABC):
    """Minimal comparable model contract."""

    model_id: str
    model_name: str

    @abstractmethod
    def fit(self, frame: pd.DataFrame, features: list[str]) -> None:
        """Fit using chronologically eligible rows."""

    @abstractmethod
    def predict(self, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
        """Return nonnegative demand predictions."""

    @abstractmethod
    def parameters(self) -> dict[str, object]:
        """Return serializable model parameters."""
