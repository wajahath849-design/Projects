# Power BI Dashboard Handoff

## Delivered dashboard

The Power BI Project is fully generated at
`powerbi/PBI/DataCenter Executive Dashboard.pbip`. It contains:

- 7 populated 1600 × 900 report pages;
- 223 native Power BI visuals;
- 17 semantic-model tables and 30 relationships;
- 56 governed DAX measures;
- a registered executive theme;
- historical, predictive, sustainability, reliability-impact, and latest
  simulation snapshot views.

Power BI imports governed CSV files rather than connecting directly to SQLite.
This avoids requiring a third-party SQLite driver and keeps report refreshes
reproducible. Raw real-time events are not imported; the dashboard receives a
compact reviewed latest-session snapshot.

## Open the correct project

If an older or empty report is already open, close it without saving over the
generated source. Then open this exact file:

`powerbi/PBI/DataCenter Executive Dashboard.pbip`

The project shown in Power BI Desktop must have these seven tabs:

1. Executive Operations Overview
2. Infrastructure Performance
3. Energy & Reliability
4. Reliability & Incident Intelligence
5. Predictive Operations
6. Cost & Sustainability
7. Reliability Impact

If only five tabs are present, the old project is open.

## Refresh sequence

1. Select **Home → Refresh** or the **Refresh now** banner.
2. If Power BI asks for privacy levels, mark every local CSV source with the
   same privacy level and approve local-file access.
3. Wait for all 17 tables to finish, then select **Close** on any old error
   dialog and refresh once more.
4. Save only after charts and cards display values.

The three advanced snapshot files should contain 792 cost/carbon rows, 1,158
incident-impact rows, and 6 latest live-operation rows. Canonical tables retain
their original row counts, including 1,727,740 server-metric records.

## Rebuild after moving or updating the project

Run these commands from the project folder before reopening Power BI:

```powershell
python scripts/export_powerbi_snapshots.py
python scripts/build_powerbi_project.py
python -m pytest tests/test_powerbi_foundation.py -q
```

The generator writes absolute local source paths for the current project
location. Rebuilding therefore repairs broken paths after the folder is moved.

## Dashboard structure

The shared layout is summary first: KPI cards, a time trend, a diagnostic
breakdown, and a detailed evidence table. Every page includes Facility and
Context slicers. Historical relative-date logic anchors to 31 December 2025,
the latest date in the canonical dataset, rather than the computer clock.

Cost and carbon values are modeled using synthetic assumptions; they are not
invoices or audited emissions. Incident before/after values are descriptive
associations, not proof of causation. Predictions and risk scores are screening
signals and require human review.

## Verification status

Automated source validation passes all 10 Power BI checks. It verifies the page
order, visual definitions, field bindings, measures, relationships, theme, and
snapshot row counts. Final pixel-level rendering and publication still require
Power BI Desktop because the desktop window is not available to this task's UI
automation session.
