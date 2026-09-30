# Changelog

## 0.1.0 — 2026-09-30

Initial portfolio release.

- Correlated synthetic commerce sources, warehouse contracts and dbt transformations.
- Data quality checks, 19 KPIs, statistical anomaly detection and driver investigation.
- Forecasts, rule-based recommendations and a separate approval boundary.
- Idempotent simulated actions, measured impact, decision ledger and outcome memory.
- Authenticated FastAPI endpoints and eleven n8n workflow exports.
- Power BI semantic model, DAX measures and nine-page report specification.
- Automated tests, recorded sample outputs and reproducible setup instructions.

Local validation: 23 tests passed; the real PostgreSQL test was skipped because no
server was available. Docker Compose configuration and dbt parsing passed. The
synthetic checkout loop completed through measured impact and a persisted lesson.
GitHub Actions is configured; its hosted run is pending publication. PostgreSQL,
n8n runtime and the Power BI Desktop report remain outstanding acceptance checks.
