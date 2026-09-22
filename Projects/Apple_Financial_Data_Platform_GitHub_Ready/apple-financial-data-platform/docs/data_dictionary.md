# Data Dictionary

## finance.Company

| Column | Type | Description |
|---|---|---|
| CompanyId | INT | Surrogate company key. |
| CIK | VARCHAR(10) | SEC Central Index Key, zero-padded. |
| CompanyName | NVARCHAR(200) | Legal entity name from SEC response. |
| Ticker | VARCHAR(20) | Reporting ticker, default `AAPL`. |
| CreatedAtUtc | DATETIME2 | Initial insert time. |
| UpdatedAtUtc | DATETIME2 | Last update time. |

## finance.Metric

| Column | Type | Description |
|---|---|---|
| MetricId | INT | Surrogate metric key. |
| MetricCode | VARCHAR(60) | Stable reporting code such as `REVENUE`. |
| MetricName | NVARCHAR(200) | User-facing label. |
| StatementName | NVARCHAR(100) | Income Statement, Balance Sheet or Cash Flow Statement. |
| CategoryName | NVARCHAR(100) | Analytical grouping. |
| DefaultUnit | VARCHAR(30) | Usually USD or USD/shares. |

## finance.FinancialFact

| Column | Type | Description |
|---|---|---|
| BusinessKey | CHAR(64) | SHA-256 key for idempotent upsert. |
| CompanyId | INT | Foreign key to company. |
| MetricId | INT | Foreign key to metric. |
| Taxonomy | VARCHAR(50) | XBRL taxonomy, currently `us-gaap`. |
| SourceTag | VARCHAR(200) | Original SEC XBRL concept. |
| FactValue | DECIMAL(28,4) | Reported or derived financial value. |
| PeriodStart / PeriodEnd | DATE | Reporting duration or instant date. |
| DurationDays | INT | Duration for flow metrics. |
| PeriodType | VARCHAR(20) | Annual or Quarterly. |
| FiscalYear | INT | Apple fiscal year derived from period end. |
| FiscalPeriod | VARCHAR(10) | FY, Q1, Q2, Q3 or Q4. |
| FormType | VARCHAR(10) | 10-K or 10-Q. |
| FiledDate | DATE | Filing date. |
| AccessionNumber | VARCHAR(30) | SEC filing accession number. |
| SourceUrl | NVARCHAR(1000) | Filing archive location. |
| IsDerived | BIT | True for calculated Q4 values. |
| DerivationMethod | NVARCHAR(300) | Derivation explanation. |
| LastRunId | UNIQUEIDENTIFIER | ETL run that last loaded the fact. |

## audit.ETLRun

Captures pipeline source, status, source row count, loaded row count, errors, warnings, start time, finish time and failure message.

## audit.DataQualityIssue

Captures validation severity, check name, metric, fiscal period, issue description and detection time.

## Reporting views

### reporting.vw_FinancialFacts
Long-form reporting dataset with company, metric, period, value and filing lineage.

### reporting.vw_FinancialSummary
One row per fiscal period with selected KPIs pivoted into columns and calculated free cash flow, margins, current ratio and leverage.

### reporting.vw_ETLRunHistory
Power BI-ready execution monitoring dataset.

### reporting.vw_DataQualityIssues
Power BI-ready data-quality issue dataset joined to ETL status.
