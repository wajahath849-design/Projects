# Step 7 — Power BI Foundation

## What and why

Step 7 creates a source-controlled Power BI Project foundation with a star schema, six imported canonical sources, a conformed date table, ten relationships, 27 foundational measures, and three empty report pages ready for visual composition.

Power BI imports the verified processed CSVs. The AI uses equivalent SQLite tables. Both are governed by the same canonical contract and KPI definitions. CSV import avoids an undeclared third-party SQLite ODBC dependency while keeping refresh reproducible.

## Files

- `powerbi/PBI/DataCenter Operations Foundation.pbip`: generated Power BI Project entry point.
- `powerbi/PBI/*.SemanticModel`: source-controlled TMDL semantic model.
- `powerbi/PBI/*.Report`: three-page report foundation.
- `powerbi/foundation/PowerQuery`: copy-ready typed M queries.
- `powerbi/foundation/DAX`: date-table and measure source.
- `powerbi/documentation/data_model.md`: model and relationship teaching guide.
- `powerbi/documentation/dax_measures.md`: definitions, formats, context, and validation.
- `powerbi/documentation/dashboard_pages.md`: three-page visual brief.
- `scripts/build_powerbi_project.py`: deterministic PBIP generator.
- `tests/test_powerbi_foundation.py`: structural foundation tests.

## Model

Dimensions: DimDate, DimFacility, DimServer.

Facts: FactServerMetrics, FactPowerMetrics, FactNetworkMetrics, FactIncidents.

Filters are single-direction from dimensions to facts. The Server-to-Incident relationship is inactive because an active relationship would create a second Facility→Server→Incident path alongside the direct Facility→Incident relationship.

## Power BI Desktop status

The PBIP project was generated and Power BI Desktop was launched against it. The Desktop process started and remained responsive, but the Windows automation helper failed twice with a local permission error and the process did not expose a titled project window during the observation period. Therefore visual/model-load validation inside Desktop is **not claimed complete**.

The project structure, JSON metadata, table count, page count, relationships, DAX presence, Power Query sources, SQL results, and Python results are automated and verified. Open the PBIP manually to complete the final Desktop gate:

```powershell
& "C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe" `
  ".\powerbi\PBI\DataCenter Operations Foundation.pbip"
```

If Desktop reports a TMDL compatibility issue, enable the Power BI Project/PBIP preview feature supported by the installed release, restart Desktop, and reopen. Do not convert or publish until the model refresh succeeds.

## Desktop verification steps

1. Open the PBIP.
2. Refresh all tables and confirm the canonical row counts.
3. Mark DimDate as the date table using `Date`.
4. Sort Month by Month Number and Quarter by Quarter Number.
5. Confirm ten relationships and that Server→Incident is inactive.
6. Create cards for the validated overall KPI values and compare them with `docs/step6_kpi_validation.json`.
7. Save the project only after values reconcile.

## Expected row counts

- DimFacility: 6.
- DimServer: 430.
- FactServerMetrics: 1,727,740.
- FactPowerMetrics: 24,108.
- FactNetworkMetrics: 24,108.
- FactIncidents: 1,158.
- DimDate: 4,018.

## Verification checklist

- [x] Star-schema roles and grains defined.
- [x] Typed Power Query sources created.
- [x] Conformed date table created.
- [x] Cardinality and filter direction documented.
- [x] Ambiguous incident path avoided.
- [x] Foundational DAX created and SQL/Python counterparts validated.
- [x] Three foundation pages created.
- [x] PBIP source project generated deterministically.
- [x] Power BI Desktop executable found and launch attempted.
- [ ] Desktop refresh and visual reconciliation completed manually; automation was blocked by local permissions.
- [ ] Final dashboard styling, which remains Step 16.

## Common errors

- File privacy prompt: classify all six local CSVs consistently and approve only local file access.
- Broken source path: edit the Power Query DataRoot parameter or regenerate the PBIP in its new location.
- Percentage displays 100× too large: values are stored on a 0–100 scale; use a literal-percent numeric format.
- Ambiguous relationship error: keep DimServer→FactIncidents inactive.
- YoY returns blank: mark DimDate as the date table and verify active date relationships.

## Interview preparation

**Why a star schema?** It makes filter propagation predictable, improves usability, and separates descriptive dimensions from measurable facts.

**Why single-direction relationships?** They reduce ambiguity and prevent facts from unexpectedly filtering dimensions or other facts.

**Why a dedicated date table?** It provides consistent year, quarter, month, and time-intelligence behavior across every fact.

**Why import CSV instead of SQLite?** Power BI Desktop has no native SQLite connector. CSV import avoids a third-party driver while using the same verified canonical data.

**How do DAX and SQL stay consistent?** Definitions share sources, aggregation, units, and filter semantics, and headline results are reconciled against SQL/Python.

## Step boundary

Steps 5–7 are complete subject to the disclosed manual Desktop refresh gate. The generic external dataset adapter remains Step 8 and has not started.

