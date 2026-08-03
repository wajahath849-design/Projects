# Forecasting and explainability (Phases 5-10)

## Feature contract

The processed dataset has one row per product, store, and date. Demand lags
(1/7/14/28/56 days) and rolling statistics (7/14/28 days) are shifted before
calculation, so the current or future target cannot enter a predictor. Historical
prices are also shifted. Calendar features and same-day opening inventory are known
at prediction time.

Natural nulls at the start of each series are retained in Parquet. Training requires
lag 1, lag 7, lag 14, and rolling mean 7. Tree candidates receive zero only for any
remaining optional null value. Missing inventory and purchase-order quantities are
documented as zero; missing supplier lead time defaults to seven days. Future event
and SNAP fields default to no known event when no future calendar plan is available.

## Evaluation and selection

All candidates use the same final seven dates as the holdout and all earlier eligible
dates as training. No random shuffle is used. The reusable rolling-origin helper
supports expanding-window folds. Reported metrics are MAE, RMSE, WAPE, sMAPE, signed
bias, residual standard deviation, training time, and inference time.

The production score weights normalized WAPE 50%, absolute bias 20%, residual
variability 20%, and inference time 10%. The lowest score wins; no model is forced.
Artifacts and parameters are stored with each SQL model run.

## Forecasts and intervals

Daily forecasts are recursively generated for 90 days. Rows 1-7 carry horizon label
7, rows 8-30 label 30, and rows 31-90 label 90. Negative predictions and lower bounds
are clipped to zero. Intervals use measured holdout residual dispersion widened by
the square root of forecast distance. Confidence is a bounded, deterministic ratio
of prediction size to interval width; it is an operational score, not a calibrated
probability.

Detail is stored in `FactForecast`. CSV exports aggregate forecast quantities and
revenue at category, store, state, and company levels. Forecast IDs are deterministic
for a model run and grain, so rerunning the generation step updates rather than
duplicates rows.

## Explainability

The selected tree model uses `shap.TreeExplainer`. The five largest absolute local
contributions per forecast are stored in `FactModelExplanation` with feature value,
signed SHAP value, direction, rank, and deterministic text. If Seasonal Naive wins,
the pipeline records a clearly labeled seasonal-component explanation instead of
claiming SHAP.

## Outputs and checks

- `data/processed/features/sample_features.parquet`
- `models/artifacts/*.joblib`
- `models/metadata/selected_model.json`
- `reports/model_evaluation/model_comparison.csv`
- `reports/model_evaluation/metric_comparison.svg`
- `reports/model_evaluation/category_errors.csv`
- `reports/model_evaluation/forecast_bias.csv`
- `reports/model_evaluation/winner_explanation.md`
- `data/exports/forecasts/forecast_detail.*`
- `data/exports/forecasts/forecast_explanations.*`

Manual SQL checks:

```sql
SELECT ModelID, ModelName, IsProduction FROM dbo.DimModel;
SELECT ModelKey, HorizonDays, WAPE, RMSE, MAE, Bias FROM dbo.FactForecastMetric;
SELECT HorizonDays, COUNT(*) Rows, MIN(ForecastQuantity) MinimumForecast
FROM dbo.FactForecast GROUP BY HorizonDays;
SELECT COUNT(*) ExplanationRows, COUNT(DISTINCT ForecastKey) ExplainedForecasts
FROM dbo.FactModelExplanation;
```
