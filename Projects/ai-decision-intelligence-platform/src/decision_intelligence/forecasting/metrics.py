"""Zero-safe forecast evaluation metrics."""

from __future__ import annotations

import numpy as np


def calculate_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """Calculate MAE, RMSE, WAPE, sMAPE, and signed forecast bias."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if actual.shape != predicted.shape or actual.size == 0:
        raise ValueError("Actual and predicted arrays must have equal nonzero shape")
    error = predicted - actual
    denominator = float(np.abs(actual).sum())
    smape_denominator = np.abs(actual) + np.abs(predicted)
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "wape": float(np.abs(error).sum() / denominator) if denominator else 0.0,
        "smape": float(np.mean(np.divide(2 * np.abs(error), smape_denominator,
            out=np.zeros_like(error), where=smape_denominator != 0))),
        "bias": float(error.mean()),
        "residual_std": float(error.std(ddof=0)),
    }
