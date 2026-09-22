CREATE OR ALTER VIEW reporting.vw_FinancialFacts
AS
SELECT
    c.CompanyName,
    c.Ticker,
    c.CIK,
    m.MetricCode,
    m.MetricName,
    m.StatementName,
    m.CategoryName,
    f.FactValue,
    f.Unit,
    f.PeriodStart,
    f.PeriodEnd,
    f.DurationDays,
    f.PeriodType,
    f.FiscalYear,
    f.FiscalPeriod,
    CASE f.FiscalPeriod
        WHEN 'Q1' THEN 1 WHEN 'Q2' THEN 2 WHEN 'Q3' THEN 3 WHEN 'Q4' THEN 4 ELSE 5
    END AS FiscalPeriodSort,
    CONCAT('FY', f.FiscalYear, ' ', f.FiscalPeriod) AS FiscalPeriodLabel,
    f.FormType,
    f.FiledDate,
    f.AccessionNumber,
    f.SourceTag,
    f.Taxonomy,
    f.SourceUrl,
    f.IsDerived,
    f.DerivationMethod,
    f.UpdatedAtUtc
FROM finance.FinancialFact f
INNER JOIN finance.Company c ON c.CompanyId = f.CompanyId
INNER JOIN finance.Metric m ON m.MetricId = f.MetricId;
GO

CREATE OR ALTER VIEW reporting.vw_FinancialSummary
AS
WITH Pivoted AS (
    SELECT
        CompanyName,
        Ticker,
        CIK,
        PeriodType,
        FiscalYear,
        FiscalPeriod,
        FiscalPeriodSort,
        FiscalPeriodLabel,
        PeriodEnd,
        MAX(CASE WHEN MetricCode = 'REVENUE' THEN FactValue END) AS Revenue,
        MAX(CASE WHEN MetricCode = 'GROSS_PROFIT' THEN FactValue END) AS GrossProfit,
        MAX(CASE WHEN MetricCode = 'OPERATING_INCOME' THEN FactValue END) AS OperatingIncome,
        MAX(CASE WHEN MetricCode = 'NET_INCOME' THEN FactValue END) AS NetIncome,
        MAX(CASE WHEN MetricCode = 'DILUTED_EPS' THEN FactValue END) AS DilutedEPS,
        MAX(CASE WHEN MetricCode = 'R_AND_D' THEN FactValue END) AS ResearchAndDevelopment,
        MAX(CASE WHEN MetricCode = 'TOTAL_ASSETS' THEN FactValue END) AS TotalAssets,
        MAX(CASE WHEN MetricCode = 'TOTAL_LIABILITIES' THEN FactValue END) AS TotalLiabilities,
        MAX(CASE WHEN MetricCode = 'EQUITY' THEN FactValue END) AS ShareholdersEquity,
        MAX(CASE WHEN MetricCode = 'CASH' THEN FactValue END) AS CashAndEquivalents,
        MAX(CASE WHEN MetricCode = 'CURRENT_ASSETS' THEN FactValue END) AS CurrentAssets,
        MAX(CASE WHEN MetricCode = 'CURRENT_LIABILITIES' THEN FactValue END) AS CurrentLiabilities,
        MAX(CASE WHEN MetricCode = 'OPERATING_CASH_FLOW' THEN FactValue END) AS OperatingCashFlow,
        MAX(CASE WHEN MetricCode = 'CAPEX' THEN FactValue END) AS CapitalExpenditure,
        MAX(CASE WHEN MetricCode = 'DIVIDENDS_PAID' THEN FactValue END) AS DividendsPaid,
        MAX(CASE WHEN MetricCode = 'SHARE_REPURCHASES' THEN FactValue END) AS ShareRepurchases
    FROM reporting.vw_FinancialFacts
    GROUP BY
        CompanyName, Ticker, CIK, PeriodType, FiscalYear, FiscalPeriod,
        FiscalPeriodSort, FiscalPeriodLabel, PeriodEnd
)
SELECT
    *,
    OperatingCashFlow - CapitalExpenditure AS FreeCashFlow,
    CAST(GrossProfit / NULLIF(Revenue, 0) AS DECIMAL(18,6)) AS GrossMarginPct,
    CAST(OperatingIncome / NULLIF(Revenue, 0) AS DECIMAL(18,6)) AS OperatingMarginPct,
    CAST(NetIncome / NULLIF(Revenue, 0) AS DECIMAL(18,6)) AS NetMarginPct,
    CAST(CurrentAssets / NULLIF(CurrentLiabilities, 0) AS DECIMAL(18,6)) AS CurrentRatio,
    CAST(TotalLiabilities / NULLIF(TotalAssets, 0) AS DECIMAL(18,6)) AS LiabilitiesToAssetsPct
FROM Pivoted;
GO

CREATE OR ALTER VIEW reporting.vw_ETLRunHistory
AS
SELECT
    RunId,
    PipelineName,
    SourceSystem,
    SourceUrl,
    Status,
    SourceRecordCount,
    LoadedRecordCount,
    ErrorCount,
    WarningCount,
    Message,
    StartedAtUtc,
    FinishedAtUtc,
    DATEDIFF(SECOND, StartedAtUtc, FinishedAtUtc) AS DurationSeconds
FROM audit.ETLRun;
GO

CREATE OR ALTER VIEW reporting.vw_DataQualityIssues
AS
SELECT
    i.IssueId,
    i.RunId,
    r.Status AS ETLRunStatus,
    i.Severity,
    i.CheckName,
    i.MetricCode,
    i.FiscalYear,
    i.FiscalPeriod,
    i.PeriodEnd,
    i.IssueDetails,
    i.DetectedAtUtc
FROM audit.DataQualityIssue i
INNER JOIN audit.ETLRun r ON r.RunId = i.RunId;
GO
