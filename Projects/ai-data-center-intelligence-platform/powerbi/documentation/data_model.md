# Power BI Analytical Model

## Purpose

The report is an import-mode star schema over the verified `data/processed`
CSV files. The AI application uses equivalent SQLite tables. Shared contracts,
KPI definitions, and generated snapshots keep the two consumer layers aligned.

## Model inventory

| Group | Tables | Grain |
|---|---|---|
| Dimensions | DimDate, DimFacility, DimServer | date, facility, server |
| Historical facts | FactServerMetrics, FactPowerMetrics, FactNetworkMetrics, FactIncidents | daily server/facility observations and incidents |
| Evidence facts | FactSystemLogs, FactAlerts, FactMaintenanceActions, FactAnomalies | one governed evidence event |
| Scored snapshots | FactServerRisk, FactFacilityHealth | server/facility score date |
| Advanced snapshots | FactCostCarbon, FactIncidentImpact, FactLiveOperationsSnapshot | facility-month, incident, latest simulated facility |
| Measures | _Measures | one centralized DAX measure home table |

The generated model contains 17 tables and 30 relationships. Dimensions filter
facts in one direction. Server-to-incident/log/alert/action relationships remain
inactive when an active facility path would otherwise create ambiguity.

## Advanced snapshot governance

`FactCostCarbon` is generated at facility-month grain from daily power history,
date-effective synthetic energy prices, and location-based synthetic carbon
factors. Its additive cost, energy, and carbon fields can be safely summed.

`FactIncidentImpact` contains one row per canonical incident. Its metric changes
compare seven days before with seven days after the incident. This supports
descriptive association only. The modeled cost-exposure field is a
time-proportional analytical proxy, not a causal loss estimate.

`FactLiveOperationsSnapshot` contains only the latest per-facility health output
from the isolated simulation database. Raw high-frequency events, logs, and
rolling states are not imported into Power BI.

## Date and refresh behavior

DimDate covers all 4,018 dates from 1 January 2015 to 31 December 2025. Monthly
advanced snapshots relate through their month-start dates, and incident impact
relates through incident date. The separate live snapshot is intentionally not
connected to DimDate because it belongs to the simulation clock.

To regenerate safely:

1. Run `python -m scripts.export_powerbi_snapshots`.
2. Run `python scripts/build_powerbi_project.py --project-root . --output powerbi/PBI`.
3. Open the PBIP file and select **Refresh** in Power BI Desktop.

The generator resolves source files from the current project folder and never
modifies the canonical SQLite history.
