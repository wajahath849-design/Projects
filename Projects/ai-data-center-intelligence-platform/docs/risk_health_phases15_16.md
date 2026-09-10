# Phases 15–16: Predictive Maintenance Risk and Health Score

## Server failure-risk screening

Every server receives a dataset-anchored seven-day risk-screening score from 0 to 100. The score is recalculated from the current database and uses a 365-day operational evidence window plus 30-day utilization averages.

Fixed maximum contributions are:

| Signal family | Points |
|---|---:|
| Hardware health and device I/O errors | 20 |
| Server service-impact events | 15 |
| Temperature and cooling signals | 15 |
| Severity-weighted incident burden | 20 |
| CPU, memory, and disk pressure | 15 |
| Repeated maintenance | 5 |
| Asset age | 10 |

The stored `signal_summary_json`, individual feature columns, primary contribution, recommendation, lookback, and method version make every result inspectable. Score bands are low below 25, moderate below 50, high below 75, and critical from 75.

This is a risk-screening heuristic, not a calibrated probability or guaranteed prediction of failure. No maintenance is triggered automatically.

## Data Center Health Score

The facility health score is a relative 0–100 triage index over the latest complete synthetic year. Its canonical weights live in `analytics/health_score_weights.yaml`:

| Dimension | Weight |
|---|---:|
| Energy efficiency | 20% |
| Reliability | 20% |
| Network health | 20% |
| Infrastructure utilization | 15% |
| Incident severity | 15% |
| Anomaly frequency | 10% |

PUE, downtime per server, latency, packet loss, severity burden, and anomaly count are lower-is-better. Network availability is higher-is-better. Network health combines availability at 50% with latency and packet loss at 25% each. Infrastructure receives a deterministic capacity-pressure penalty only above 70% average CPU-memory-disk utilization.

Every row stores all six component scores, the overall score, weight version, and exact weight JSON. The language model cannot select or change weights.

## Reproduction

`scripts/score_operations.py` writes the two CSV artifacts, applies the advanced schema, loads the six explicitly simulated incident reviews, and refreshes both score tables transactionally. A full `scripts/load_database.py` rebuild derives the same two score tables after loading canonical evidence and aggregates.

## Validation status

Coverage, bounds, JSON evidence, fixed-weight reconciliation, and cautious recommendation tests pass. The accepted audit contains 430 server-risk rows and 6 facility-health rows with database integrity `ok` and zero foreign-key violations.

## Limitations

- The seven-day label is a screening horizon; the synthetic dataset has no observed future-failure label for probability calibration.
- Relative facility normalization means scores can change when facilities are added or removed.
- A high score means prioritize review, not perform an automatic change.
- Real deployment requires calibrated outcomes, drift monitoring, safety approval, and role-based access.
