# Step 6 — Shared KPI Definition Layer

## What and why

Step 6 creates a shared semantic definition layer for AI/SQL and Power BI. It prevents identical labels from using different aggregations, denominators, units, or time logic.

## Files

- `analytics/metric_definitions.yaml`: 18 canonical measures.
- `analytics/business_glossary.yaml`: terms, synonyms, meanings, and caveats.
- `analytics/kpi_catalog.yaml`: primary KPIs, drivers, guardrails, dimensions, and review cadence.
- `scripts/validate_kpis.py`: SQL-to-pandas reconciliation.
- `docs/step6_kpi_validation.json`: exact measured results.
- `tests/test_kpis.py`: catalog and numerical validation tests.

## KPI framework

Primary operational outcomes:

- Average PUE: energy efficiency.
- Operational Availability: server-minute service health.
- Total Downtime: customer/operation-impact proxy.
- Network Availability: measured connectivity health.

Drivers cover energy, incidents, capacity/utilization, latency, packet loss, cooling cost, and year-over-year movement. Guardrails separate operational from network availability, preserve the loaded-data date anchor, label synthetic cost honestly, and prohibit invented targets.

## Important decisions

- Average PUE is an arithmetic mean of daily PUE observations under the active context.
- Incident Rate is incidents per 100 visible servers; the 11-year overall value can exceed 100 because servers can have multiple incidents.
- Operational Availability uses incident downtime divided by potential server-minutes.
- Relative dates anchor to the maximum loaded timestamp, 31 Dec 2025.
- No targets were set because no operational owner or target-setting exercise exists.

## Measured validation

All 18 SQL values reconcile with independent pandas calculations within numerical tolerance. Headline overall values include:

- Average PUE: 1.476205.
- Total downtime: 73,559 minutes.
- Incident count: 1,158.
- Active server count: 407.
- Network availability: 99.961103%.
- Operational availability: 99.997043%.
- 2025 vs 2024 PUE change: -1.030164%.
- 2025 vs 2024 cooling-cost change: +0.235301%.
- 2025 vs 2024 downtime change: +34.494510%.

These values are descriptive measurements from synthetic data, not targets or business-impact claims.

## Commands

```powershell
python scripts\validate_kpis.py
python -m pytest tests\test_kpis.py -q
```

Expected: `all_passed: true` for all 18 metrics and three passing tests.

## Verification checklist

- [x] Metric names, sources, formulas, units, direction, and caveats defined.
- [x] Primary outcomes separated from drivers and guardrails.
- [x] Availability definitions separated.
- [x] Relative-date policy defined.
- [x] Synthetic cost labeled honestly.
- [x] No unsupported targets invented.
- [x] SQL and Python reconcile for all metrics.

## Interview preparation

**Why use a semantic KPI layer?** It gives every consumer the same definition and prevents dashboard-versus-AI disagreements.

**Measure or calculated column?** Aggregated KPIs are measures because they must respond to filter context; calculated columns store row-level results.

**Why separate outcomes, drivers, and guardrails?** Outcomes show health, drivers explain movement, and guardrails prevent misleading optimization.

**How do you validate DAX without fabricating success?** First reconcile equivalent SQL and Python. Then validate DAX inside Power BI once the model loads; absence of Desktop execution is disclosed.

