# Dashboard Layout Specification

Canvas: 16:9, 1280 × 720. Background: `#F5F5F7`. Use 24 px outer margins and 16 px gaps.

## Page 1 — Executive Overview

- Header: title, source subtitle and last refresh time.
- Row 1: six KPI cards — Revenue, Net Income, Operating Cash Flow, Free Cash Flow, Gross Margin and Revenue YoY.
- Row 2 left (65%): combo chart with Revenue columns and Net Income line by FiscalPeriodLabel.
- Row 2 right (35%): margin trend with Gross, Operating and Net Margin.
- Bottom left: Free Cash Flow waterfall.
- Bottom right: latest period financial summary table.
- Top-right slicers: Period Type, Fiscal Year and Fiscal Period.

## Page 2 — Profitability Analysis

- Four KPI cards: Revenue, Gross Profit, Operating Income and Net Income.
- Main chart: four-line profitability trend.
- Secondary chart: R&D and R&D % of Revenue.
- Matrix: Fiscal period rows and core profitability metrics as values.

## Page 3 — Cash Flow and Liquidity

- KPI cards: Operating Cash Flow, Capex, Free Cash Flow, Current Ratio.
- Combo chart: OCF and Capex columns, FCF line.
- Stacked columns: Dividends Paid and Share Repurchases.
- Line chart: Cash and Equivalents.

## Page 4 — Balance Sheet

- KPI cards: Assets, Liabilities, Equity and Cash.
- Area or line chart: Assets, Liabilities and Equity trend.
- Columns: Current Assets versus Current Liabilities.
- Gauge or KPI: Liabilities to Assets %.

## Page 5 — Data Quality and Pipeline Monitoring

- KPI cards: Latest ETL Status, Latest Refresh, Loaded Rows, Errors and Warnings.
- Line chart: DurationSeconds by StartedAtUtc.
- Columns: LoadedRecordCount by run.
- Detail table: Severity, CheckName, MetricCode, FiscalPeriod, IssueDetails.
