import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing


def forecast(values, horizon=30, bounded=False) -> dict:
    """Fit only supplied pre-incident history; approximate 95% predictive intervals."""
    series = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    if series.notna().sum() < 28:
        raise ValueError("At least 28 finite daily observations are required")
    series = series.loc[series.first_valid_index():].reset_index(drop=True)
    imputed = int(series.isna().sum())
    for index in series.index[series.isna()]:
        prior_weekdays = series.iloc[:index][series.index[:index] % 7 == index % 7].dropna()
        if len(prior_weekdays) < 2:
            raise ValueError("Insufficient prior same-weekday history to impute a quality gap")
        series.iloc[index] = float(prior_weekdays.tail(8).median())
    fitted = ExponentialSmoothing(series.to_numpy(), trend="add", damped_trend=True,
                                  seasonal="add", seasonal_periods=7,
                                  initialization_method="estimated").fit(optimized=True)
    center = np.maximum(0, fitted.forecast(horizon))
    scale = max(float(np.std(fitted.resid, ddof=1)), 1e-6)
    width = 1.96*scale*np.sqrt(1+np.arange(1, horizon+1)/7)
    cap = 1 if bounded else np.inf
    return {"expected": np.clip(center, 0, cap).tolist(), "lower": np.clip(center-width, 0, cap).tolist(),
            "upper": np.clip(center+width, 0, cap).tolist(), "method": "damped_additive_holt_winters",
            "residual_sd": scale, "training_rows": len(series), "imputed_rows": imputed}
