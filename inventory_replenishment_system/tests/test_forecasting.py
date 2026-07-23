from datetime import date, timedelta

import pandas as pd

from app.forecasting import forecast_group


def test_sparse_history_uses_fallback() -> None:
    start = date(2026, 1, 1)
    group = pd.DataFrame(
        {
            "date": [start + timedelta(days=i) for i in range(30)],
            "demand_qty": [0 if i % 3 else 5 for i in range(30)],
        }
    )
    result = forecast_group(group, horizon_days=14, min_training_days=90)
    assert result.model_name == "seasonal_naive"
    assert len(result.forecast) == 14
    assert (result.forecast["forecast_qty"] >= 0).all()


def test_dense_history_produces_forecast() -> None:
    start = date(2025, 1, 1)
    group = pd.DataFrame(
        {
            "date": [start + timedelta(days=i) for i in range(160)],
            "demand_qty": [10 + (i % 7) + (i / 100) for i in range(160)],
        }
    )
    result = forecast_group(group, horizon_days=10, min_training_days=90)
    assert len(result.forecast) == 10
    assert (result.forecast["upper_qty"] >= result.forecast["lower_qty"]).all()
    assert result.metrics["sample_count"] > 0
    assert result.metrics["absolute_error_sum"] >= 0
    assert result.metrics["actual_sum"] >= 0
    assert result.metrics["forecast_sum"] >= 0
