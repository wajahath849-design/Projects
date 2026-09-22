# Testing and Verification

## Automated tests

```powershell
pytest --cov=apple_financial_etl --cov-report=term-missing
```

The unit tests use an offline SEC-shaped JSON fixture and do not call the internet.

## Manual pipeline checks

1. Run `apple-finance-etl run --csv-only --force-refresh`.
2. Confirm a raw Company Facts JSON file appears in `data/raw`.
3. Confirm financial facts and quality issue CSV files appear in `data/processed`.
4. Inspect Q2 and Q3 duration metrics and verify they represent approximately three months rather than cumulative year-to-date durations.
5. Confirm derived Q4 rows have `is_derived = True` and a derivation description.
6. Run the same ETL twice and confirm SQL row counts do not duplicate.
7. Open `reporting.vw_ETLRunHistory` and confirm both runs are recorded.
8. Open `reporting.vw_FinancialFacts` and follow `SourceUrl` or `AccessionNumber` back to the filing.

## SQL validation queries

```sql
-- Duplicate reporting grain: expected zero rows
SELECT CIK, MetricCode, PeriodEnd, PeriodType, FiscalPeriod, Unit, COUNT(*) AS RowCount
FROM reporting.vw_FinancialFacts
GROUP BY CIK, MetricCode, PeriodEnd, PeriodType, FiscalPeriod, Unit
HAVING COUNT(*) > 1;

-- Latest pipeline executions
SELECT TOP (20) *
FROM reporting.vw_ETLRunHistory
ORDER BY StartedAtUtc DESC;

-- Latest quality issues
SELECT TOP (100) *
FROM reporting.vw_DataQualityIssues
ORDER BY DetectedAtUtc DESC;
```
