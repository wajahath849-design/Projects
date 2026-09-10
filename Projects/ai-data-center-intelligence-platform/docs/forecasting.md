# Multi-Metric Forecasting

Future-year questions bypass text-to-SQL and use a governed statistical forecasting route. The route detects the requested metric, reads its annual history from the current SQLite database, refits a separate linear trend for the fleet and each facility, performs rolling-origin backtesting, and returns an estimate with an approximate 95% prediction interval.

Supported metrics are PUE, average power draw, IT load, cooling power, annual cooling cost, CPU/memory/disk/server-network utilization, bandwidth utilization, latency, packet loss, throughput, network availability, annual downtime, and annual incident count.

Examples:

```text
What will cooling be in 2030?
Estimate the price of cooling in 2030.
What will Frankfurt network latency be in 2030?
How much downtime will there be in 2030?
What will CPU utilization be in 2030?
```

“Cooling” maps to average cooling power. “Price/cost of cooling” maps to the only monetary series in the dataset: annual cooling cost. The database does not contain electricity tariffs, hardware prices, historical facility capacity, or server-inventory snapshots, so those future values are not estimated. Adding a genuine historical time series and a governed metric definition is required before forecasting them.

## Automatic updates

No forecast values are hard-coded or cached. Each future question reads and refits from `database/datacenter.db`. Annual model history is read from the governed `agg_facility_yearly` summary, which is rebuilt from canonical raw rows whenever the database is loaded. If that derived table is absent in an older database, the forecaster safely falls back to the original raw-table query. After updating canonical processed data, rebuild the database:

```powershell
python scripts\load_database.py
python scripts\evaluate_forecasts.py
python scripts\ask.py "Estimate the price of cooling in 2030"
```

The training end year and predictions will change when a newer complete year is present. An incomplete latest calendar year is excluded to avoid comparing partial and full annual periods.

The parser accepts a future year anywhere in the question, so “cooling 2030” and “forecast cooling for 2030” are equivalent. “Next year,” “5 years from now,” and word-number phrases such as “five years from now” resolve relative to the latest complete database year. If forecast intent is present but no date can be resolved, the assistant asks which future year to use instead of silently running a historical query.

Multiple questions separated by question marks, semicolons, or new lines are executed independently and returned as numbered answers. A single future question may also request multiple metrics, for example `Forecast PUE, cooling cost, and latency in 2030`. Each metric is modeled separately because units and aggregation semantics differ; mixed-unit results are shown in one evidence table rather than a misleading combined chart.

The chat UI remembers the most recently discussed metric, facility, and year. A follow-up such as `2040`, `what about Dublin?`, or `and PUE?` is expanded into a standalone data question before routing. If there is no usable context, the assistant asks for the missing metric or year instead of guessing. Generic `price` means Annual Cooling Cost because it is the dataset's only monetary time series. Historical price comparisons and increase/decrease questions are answered directly from current database history.

## Interpretation

`r_squared` describes how strongly a straight historical trend fits the annual values. `backtest_mae` measures rolling one-year-ahead absolute error in the metric's native unit. Low-fit metrics such as volatile incident or downtime series receive an explicit low-confidence warning. A tight interval on synthetic data does not establish real-world certainty.

This initial model is transparent and easy to audit. It does not incorporate planned capacity, electricity tariffs, weather, hardware changes, causal drivers, or scenario assumptions. Those would require additional data and a more appropriate multivariate or scenario model.
