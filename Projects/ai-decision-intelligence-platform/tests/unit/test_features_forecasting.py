"""Unit coverage for Phases 5-10 leakage, metrics, splits, and outputs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from decision_intelligence.explainability.explanation_writer import explanation_text
from decision_intelligence.features.calendar_features import add_calendar_features
from decision_intelligence.features.lag_features import add_lag_features
from decision_intelligence.features.price_features import add_price_features
from decision_intelligence.forecasting.cross_validation import rolling_origin_splits
from decision_intelligence.forecasting.forecast_generator import _future_row
from decision_intelligence.forecasting.metrics import calculate_metrics
from decision_intelligence.forecasting.seasonal_naive import SeasonalNaiveModel


def _series_frame(size: int = 60) -> pd.DataFrame:
    return pd.DataFrame({
        "product_id": ["P1"] * size,
        "store_id": ["S1"] * size,
        "category_id": ["C1"] * size,
        "date": pd.date_range("2024-01-01", periods=size),
        "target": np.arange(1, size + 1, dtype=float),
        "current_price": np.arange(10, 10 + size, dtype=float),
    })


def test_lags_and_rolls_use_only_prior_targets() -> None:
    result = add_lag_features(_series_frame())
    assert result.loc[7, "lag_7"] == 1
    assert result.loc[7, "rolling_mean_7"] == 4
    assert result.loc[28, "rolling_min_28"] == 1
    assert result.loc[28, "rolling_max_28"] == 28
    assert pd.isna(result.loc[6, "rolling_mean_7"])


def test_price_lags_are_historical() -> None:
    result = add_price_features(_series_frame())
    assert result.loc[7, "price_lag_7"] == 10
    assert result.loc[28, "price_lag_28"] == 10
    assert result.loc[28, "promotion_proxy"] == 0


def test_calendar_features_are_deterministic() -> None:
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2024-01-06")], "event_name": ["Event"],
        "event_type": ["Cultural"], "snap_ca": [1], "snap_tx": [0], "snap_wi": [0],
    })
    result = add_calendar_features(frame)
    assert result.loc[0, "weekend_flag"] == 1
    assert result.loc[0, "event_flag"] == 1
    assert result.loc[0, "snap_flag"] == 1


def test_metrics_are_zero_safe_and_signed() -> None:
    metrics = calculate_metrics(np.array([0.0, 2.0]), np.array([0.0, 3.0]))
    assert metrics["mae"] == pytest.approx(0.5)
    assert metrics["wape"] == pytest.approx(0.5)
    assert metrics["bias"] == pytest.approx(0.5)


def test_rolling_origin_splits_are_chronological() -> None:
    dates = pd.date_range("2024-01-01", periods=30)
    splits = rolling_origin_splits(pd.Series(dates), horizon=7, max_folds=3)
    assert len(splits) == 3
    assert all(train_end < test_end for train_end, test_end in splits)
    assert splits == sorted(splits)


def test_seasonal_naive_predicts_lag_seven() -> None:
    frame = pd.DataFrame({"lag_7": [2.0, 3.0], "target": [4.0, 5.0]})
    model = SeasonalNaiveModel()
    model.fit(frame, ["lag_7"])
    assert model.predict(frame, ["lag_7"]).tolist() == [2.0, 3.0]


def test_future_features_do_not_read_future_actuals() -> None:
    last = _series_frame(20).iloc[-1].copy()
    last["product_code"] = 0
    last["store_code"] = 0
    last["state_id"] = "CA"
    last["current_stock"] = 100
    last["supplier_lead_time"] = 7
    row = _future_row(last, pd.Timestamp("2024-02-01"), list(range(1, 21)))
    assert row["lag_1"] == 20
    assert row["lag_7"] == 14
    assert row["rolling_mean_7"] == pytest.approx(17)


def test_explanation_text_reflects_direction() -> None:
    assert "increased" in explanation_text("lag_7", 4, 1.25)
    assert "decreased" in explanation_text("current_price", 8.5, -0.5)
