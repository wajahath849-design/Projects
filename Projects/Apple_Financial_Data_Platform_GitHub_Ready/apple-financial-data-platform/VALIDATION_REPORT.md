# Validation Report

Validation date: 2026-08-03

## Completed checks

- Python source and tests compile successfully.
- Seven automated tests pass.
- Quarter-only income-statement selection is verified.
- Cumulative Q2/Q3 cash-flow normalization is verified.
- Later-filed values replace older values at the same reporting grain.
- Fiscal Q4 flow derivation is verified.
- Fiscal year-end balance-sheet values are reclassified as Q4 snapshots with lineage.
- Duplicate reporting grain check returns zero duplicates for the offline sample.
- Offline sample generation produces 17 curated rows and zero quality issues.
- The Power BI theme validates against Microsoft's `reportThemeSchema-2.156.json` schema.
- All JSON project files parse successfully.

## Environment-dependent checks

The build environment did not contain SQL Server, Docker or the Microsoft ODBC driver and did not permit direct outbound access from Python. Therefore, the following must be executed on the target Windows machine:

1. Live SEC EDGAR Company Facts download.
2. SQL Server database creation and DDL execution.
3. SQL staging and idempotent upsert execution.
4. Power BI Desktop connection and visual rendering.

The repository includes retry logic, SQL initialization scripts, an offline sample, exact execution commands and Power BI implementation files for these steps.
