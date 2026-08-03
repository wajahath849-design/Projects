# Demand forecasting model card

## Intended use

Daily product-store demand forecasting for a synthetic sample derived from the M5 schema,
feeding inventory-risk analysis and replenishment optimization. It is for portfolio
demonstration and analytical education, not autonomous purchasing decisions.

## Candidates and selection

Seasonal Naive, XGBoost, and LightGBM use the same leakage-safe features and chronological
holdout. The production score weights normalized WAPE 50%, absolute bias 20%, residual
variability 20%, and inference time 10%. No model is privileged by name.

Measured sample results from the verified run:

| Model | WAPE | RMSE | MAE | sMAPE | Bias |
|---|---:|---:|---:|---:|---:|
| XGBoost | 0.370938 | 2.009816 | 1.682468 | 0.423485 | -0.399315 |
| LightGBM | 0.396078 | 2.164964 | 1.796496 | 0.459258 | -0.615553 |
| Seasonal Naive | 0.464567 | 2.542496 | 2.107143 | 0.497173 | 0.642857 |

XGBoost won that sample run. These values are not claims about full M5 or future data;
retraining can select a different production model.

## Features and leakage controls

Calendar, lag 1/7/14/28/56, shifted rolling statistics, historical price signals, and
point-in-time inventory signals. Targets and price histories are shifted before rolling
operations. All splits preserve time order and never shuffle.

## Explainability and uncertainty

Tree winners use `shap.TreeExplainer`; five local contributions are stored per forecast.
Text explanations are deterministic. Prediction intervals use measured holdout residual
dispersion widened by forecast distance; confidence is an operational interval-width score,
not a calibrated probability.

## Limitations and monitoring

- The bundled sample has only 28 historical dates; long lags are unavailable for training.
- Recursive 90-day forecasts accumulate error.
- Unknown future events default to inactive.
- Synthetic supplier, warehouse, transport, and inventory records are not real operations.
- Monitor WAPE, bias, coverage, data quality, drift, stockout outcomes, and recommendation
  feasibility before any real-world use. Require human approval for purchasing decisions.
