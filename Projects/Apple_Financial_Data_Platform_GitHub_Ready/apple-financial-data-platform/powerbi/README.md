# Power BI Implementation Guide

## Load the model

In Power BI Desktop, choose **Get data → SQL Server**.

- Server: `localhost,1433` or your configured SQL Server instance.
- Database: `AppleFinancialReporting`.
- Data connectivity mode: Import for a portfolio project; DirectQuery is optional.

Select:

- `reporting.vw_FinancialSummary` as `FinancialSummary`
- `reporting.vw_FinancialFacts` as `FinancialFacts`
- `reporting.vw_ETLRunHistory` as `ETLRunHistory`
- `reporting.vw_DataQualityIssues` as `DataQualityIssues`

## Model relationships

The views are intentionally usable without complex relationships. For the recommended model:

1. Create a `Fiscal Period` dimension from distinct `FiscalYear`, `FiscalPeriod`, `PeriodType`, `PeriodEnd` and `FiscalPeriodSort` values in `FinancialSummary`.
2. Create a one-to-many relationship from the period dimension to `FinancialSummary` and `FinancialFacts` using a calculated `PeriodKey`.
3. Keep ETL and data-quality tables separate; relate `DataQualityIssues[RunId]` to `ETLRunHistory[RunId]` as many-to-one.
4. Sort `FiscalPeriod` by `FiscalPeriodSort`.

Suggested calculated key in both financial tables:

```DAX
PeriodKey =
FinancialSummary[PeriodType] & "|" &
FORMAT(FinancialSummary[FiscalYear], "0000") & "|" &
FinancialSummary[FiscalPeriod]
```

## Theme

Import `AppleFinanceTheme.json` through **View → Themes → Browse for themes**.

## Measures

Create a measures table and paste the measures from `measures.dax`.

## Recommended report pages

### 1. Executive Overview

- KPI cards: Revenue, Net Income, Operating Cash Flow, Free Cash Flow, Gross Margin and Net Margin.
- Line and clustered column chart: Revenue and Net Income by fiscal year or quarter.
- Line chart: Gross, operating and net margins.
- Waterfall: Operating Cash Flow to Free Cash Flow.
- Slicers: Period Type, Fiscal Year and Fiscal Period.

### 2. Profitability Analysis

- Revenue, Gross Profit, Operating Income and Net Income trend.
- R&D trend and R&D as a percentage of Revenue.
- Margin trend.
- Matrix by fiscal period with conditional formatting.

### 3. Cash Flow and Liquidity

- Operating Cash Flow, Capital Expenditure and Free Cash Flow trend.
- Dividends and Share Repurchases.
- Cash and Equivalents.
- Current Ratio and Current Assets versus Current Liabilities.

### 4. Balance Sheet

- Total Assets, Total Liabilities and Shareholders' Equity.
- Liabilities-to-Assets percentage.
- Cash, Inventory and Accounts Receivable.
- Balance sheet composition by fiscal period.

### 5. Data Quality and ETL Monitoring

- Latest ETL Status.
- Last Refresh UTC.
- Loaded Record Count.
- Error and Warning Count.
- Run duration trend.
- Quality issues table with Severity, CheckName, FiscalYear, MetricCode and IssueDetails.

## Formatting standards

- Use display units in billions for financial amounts.
- Use two decimals for ratios and percentages.
- Use a single fiscal period selection for KPI cards.
- Add tooltips for filing date, accession number, XBRL source tag and derived-Q4 indicator.
- Add a source note: `Source: U.S. SEC EDGAR XBRL filings; transformed by project ETL.`
