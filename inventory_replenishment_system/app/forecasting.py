from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_mean_7",
    "rolling_mean_28",
    "rolling_mean_90",
    "rolling_std_28",
    "day_of_week",
    "week_of_year",
    "month",
    "day_of_month",
    "is_weekend",
]


@dataclass(frozen=True)
class ForecastResult:
    forecast: pd.DataFrame
    metrics: dict[str, float | int | None]
    model_name: str
    warning: str | None = None


def prepare_daily_demand(transactions: pd.DataFrame) -> pd.DataFrame:
    required = {"transaction_ts", "warehouse_id", "sku_id", "transaction_type", "quantity"}
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(f"Missing transaction columns: {sorted(missing)}")

    outbound_types = {"SALE", "TRANSFER_OUT", "DAMAGE"}
    data = transactions[transactions["transaction_type"].isin(outbound_types)].copy()
    data["date"] = pd.to_datetime(data["transaction_ts"], utc=True).dt.date
    data["demand_qty"] = pd.to_numeric(data["quantity"], errors="coerce").abs()
    data = data.dropna(subset=["date", "demand_qty"])
    return (
        data.groupby(["warehouse_id", "sku_id", "date"], as_index=False)["demand_qty"]
        .sum()
        .sort_values(["warehouse_id", "sku_id", "date"])
    )


def _continuous_series(group: pd.DataFrame) -> pd.Series:
    if group.empty:
        raise ValueError("Cannot forecast an empty demand group")
    series = group.set_index(pd.to_datetime(group["date"]))["demand_qty"].astype(float).sort_index()
    operational_end = max(series.index.max(), pd.Timestamp(date.today() - pd.Timedelta(days=1)))
    full_index = pd.date_range(series.index.min(), operational_end, freq="D")
    return series.reindex(full_index, fill_value=0.0).rename("y")


def _feature_frame(series: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"y": series.astype(float)})
    for lag in (1, 7, 14, 28):
        df[f"lag_{lag}"] = df["y"].shift(lag)
    shifted = df["y"].shift(1)
    df["rolling_mean_7"] = shifted.rolling(7, min_periods=2).mean()
    df["rolling_mean_28"] = shifted.rolling(28, min_periods=7).mean()
    df["rolling_mean_90"] = shifted.rolling(90, min_periods=14).mean()
    df["rolling_std_28"] = shifted.rolling(28, min_periods=7).std().fillna(0.0)
    idx = df.index
    df["day_of_week"] = idx.dayofweek
    df["week_of_year"] = idx.isocalendar().week.astype(int)
    df["month"] = idx.month
    df["day_of_month"] = idx.day
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    return df.replace([np.inf, -np.inf], np.nan).dropna(subset=FEATURE_COLUMNS)


def _future_features(history: pd.Series, target_date: pd.Timestamp) -> pd.DataFrame:
    values = history.astype(float)

    def lag(days: int) -> float:
        target = target_date - pd.Timedelta(days=days)
        if target in values.index:
            return float(values.loc[target])
        return float(values.iloc[-1]) if len(values) else 0.0

    shifted = values.iloc[-90:]
    row = {
        "lag_1": lag(1),
        "lag_7": lag(7),
        "lag_14": lag(14),
        "lag_28": lag(28),
        "rolling_mean_7": float(values.iloc[-7:].mean()) if len(values) else 0.0,
        "rolling_mean_28": float(values.iloc[-28:].mean()) if len(values) else 0.0,
        "rolling_mean_90": float(shifted.mean()) if len(shifted) else 0.0,
        "rolling_std_28": float(values.iloc[-28:].std(ddof=1)) if len(values) > 1 else 0.0,
        "day_of_week": target_date.dayofweek,
        "week_of_year": int(target_date.isocalendar().week),
        "month": target_date.month,
        "day_of_month": target_date.day,
        "is_weekend": int(target_date.dayofweek >= 5),
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS)


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float | int | None]:
    if len(actual) == 0:
        return {
            "mae": None,
            "rmse": None,
            "wape": None,
            "bias": None,
            "sample_count": 0,
            "absolute_error_sum": 0.0,
            "actual_sum": 0.0,
            "forecast_sum": 0.0,
        }
    error = predicted - actual
    denominator = np.abs(actual).sum()
    absolute_error_sum = float(np.abs(error).sum())
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "wape": float(absolute_error_sum / denominator) if denominator > 0 else None,
        "bias": float(error.mean()),
        "sample_count": int(len(actual)),
        "absolute_error_sum": absolute_error_sum,
        "actual_sum": float(actual.sum()),
        "forecast_sum": float(predicted.sum()),
    }


def _seasonal_naive(series: pd.Series, horizon_days: int) -> ForecastResult:
    future_dates = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    recent = series.iloc[-56:] if len(series) >= 56 else series
    weekday_means = recent.groupby(recent.index.dayofweek).mean()
    fallback = float(recent.mean()) if len(recent) else 0.0
    predictions = np.array([max(0.0, float(weekday_means.get(d.dayofweek, fallback))) for d in future_dates])
    residual_std = float(recent.std(ddof=1)) if len(recent) > 1 else 0.0
    interval = 1.2816 * residual_std
    forecast = pd.DataFrame(
        {
            "forecast_date": future_dates.date,
            "forecast_qty": predictions,
            "lower_qty": np.maximum(0.0, predictions - interval),
            "upper_qty": predictions + interval,
        }
    )
    return ForecastResult(
        forecast=forecast,
        metrics={
            "mae": None,
            "rmse": None,
            "wape": None,
            "bias": None,
            "sample_count": 0,
            "absolute_error_sum": 0.0,
            "actual_sum": 0.0,
            "forecast_sum": 0.0,
        },
        model_name="seasonal_naive",
        warning="Insufficient or sparse history for LightGBM; seasonal-naive fallback used.",
    )


def forecast_group(
    group: pd.DataFrame,
    horizon_days: int = 90,
    min_training_days: int = 90,
    random_state: int = 42,
) -> ForecastResult:
    series = _continuous_series(group)
    non_zero_days = int((series > 0).sum())
    if len(series) < min_training_days or non_zero_days < 28:
        return _seasonal_naive(series, horizon_days)

    features = _feature_frame(series)
    if len(features) < 60:
        return _seasonal_naive(series, horizon_days)

    holdout_days = min(28, max(7, len(features) // 5))
    train = features.iloc[:-holdout_days]
    validation = features.iloc[-holdout_days:]

    model = LGBMRegressor(
        objective="regression_l1",
        n_estimators=350,
        learning_rate=0.035,
        num_leaves=31,
        max_depth=-1,
        min_child_samples=20,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_alpha=0.05,
        reg_lambda=0.2,
        random_state=random_state,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(train[FEATURE_COLUMNS], train["y"])
    validation_prediction = np.maximum(0.0, model.predict(validation[FEATURE_COLUMNS]))
    metrics = _metrics(validation["y"].to_numpy(), validation_prediction)
    residual_std = float(np.std(validation_prediction - validation["y"].to_numpy(), ddof=1))
    if not np.isfinite(residual_std):
        residual_std = 0.0

    # Refit on all available data before producing the operational forecast.
    model.fit(features[FEATURE_COLUMNS], features["y"])
    history = series.copy()
    rows: list[dict[str, object]] = []
    interval = 1.2816 * residual_std  # Approximate 80% interval; replace with conformal intervals if required.
    for target_date in pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D"):
        x_future = _future_features(history, target_date)
        prediction = max(0.0, float(model.predict(x_future)[0]))
        rows.append(
            {
                "forecast_date": target_date.date(),
                "forecast_qty": prediction,
                "lower_qty": max(0.0, prediction - interval),
                "upper_qty": prediction + interval,
            }
        )
        history.loc[target_date] = prediction

    return ForecastResult(
        forecast=pd.DataFrame(rows),
        metrics=metrics,
        model_name="lightgbm_lag_features",
    )
