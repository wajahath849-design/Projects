# Interview guide

## Two-minute explanation

The project turns demand history into decisions. It validates and models M5-shaped retail
data, compares three forecasting approaches chronologically, explains the measured winner,
calculates inventory risk, and uses a mixed-integer solver to select supplier/warehouse order
quantities subject to operational constraints. Scenarios, an API, and a Power BI package make
the results usable and auditable.

## Design decisions to discuss

- Time splits and shifted rolling windows prevent target leakage.
- Model selection is metric-driven; the sample selected XGBoost, not the nominated primary.
- SQL decimal values remain unrounded inside optimization; only presentation is formatted.
- Every solver output is independently revalidated before persistence.
- SHAP text is deterministic, making explanations reproducible.
- Baseline scenario fields are stored beside scenario fields, preventing accidental overwrite.
- Windows-authenticated SQL Express is the primary local path; SQL auth is isolated to CI/Docker.

## Honest limitations

The sample is tiny and synthetic outside M5-shaped sales. Uncertainty is residual-based,
scenario response functions are deterministic assumptions, and the API lacks production auth.
Power BI assets are construction instructions and exports, not a PBIX. The platform is
production-style, not production-ready.

## Likely questions

- **Why XGBoost?** It had the lowest measured weighted selection score in this sample.
- **Why not random split?** Random splitting leaks future time-series information.
- **How is infeasibility handled?** The solver maps statuses and emits constraint-specific
  diagnostics; recommendations persist only after independent validation.
- **How would you scale it?** Partition Parquet and SQL loads, use rolling-origin backtests,
  parallelize independent series, calibrate intervals, add orchestration and model monitoring.
