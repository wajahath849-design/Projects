# Synthetic Data Center Operations Dataset — 2015 to 2025

This dataset was generated for the **AI-Powered Data Center Operations Intelligence Platform**.

## Period
- Start: 2015-01-01
- End: 2025-12-31
- This is the full inclusive 2015–2025 range, i.e. **11 calendar years**.
- Random seed: 42

## Scope
- 6 facilities
- 430 servers
- Daily server, power and network measurements
- Incident history
- Long-term trends plus deliberately injected operational anomalies

## Folders
- `raw/`: deliberately contains a small controlled number of missing values, duplicates, outliers and inconsistent labels.
- `processed/`: canonical clean data for SQLite, AI/RAG and Power BI.
- `metadata/`: KPI definitions, business glossary, data contract and manifest.
- `adapters/`: templates for mapping future external data-center datasets into the canonical model.
- `evaluation/`: known ground-truth anomaly windows. **Do not expose this folder to the RAG knowledge base.**

## Canonical tables
1. `facilities.csv`
2. `servers.csv`
3. `server_metrics.csv`
4. `power_metrics.csv`
5. `network_metrics.csv`
6. `uptime_incidents.csv`

## Long-term behavior
The data includes:
- gradual workload growth,
- gradual infrastructure-efficiency improvement,
- seasonal cooling effects,
- rising network demand,
- realistic incident distributions,
- known cooling/network/power/workload anomaly windows.

## External dataset compatibility
The future application should use:
External data → schema detection → alias mapping → type/unit normalization → canonical model → SQLite / Power BI / AI.

A future compatible dataset does not need every module. Missing domains should be disabled gracefully.
