CREATE OR ALTER PROCEDURE reporting.usp_GetFinancialFacts
    @StartFiscalYear INT = NULL,
    @EndFiscalYear INT = NULL,
    @PeriodType VARCHAR(20) = NULL,
    @StatementName NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT *
    FROM reporting.vw_FinancialFacts
    WHERE (@StartFiscalYear IS NULL OR FiscalYear >= @StartFiscalYear)
      AND (@EndFiscalYear IS NULL OR FiscalYear <= @EndFiscalYear)
      AND (@PeriodType IS NULL OR PeriodType = @PeriodType)
      AND (@StatementName IS NULL OR StatementName = @StatementName)
    ORDER BY FiscalYear, FiscalPeriodSort, StatementName, MetricName;
END;
GO

CREATE OR ALTER PROCEDURE reporting.usp_GetLatestFinancialSnapshot
AS
BEGIN
    SET NOCOUNT ON;

    WITH LatestPeriod AS (
        SELECT TOP (1) PeriodType, FiscalYear, FiscalPeriod, PeriodEnd
        FROM reporting.vw_FinancialSummary
        ORDER BY PeriodEnd DESC,
                 CASE WHEN PeriodType = 'Quarterly' THEN 1 ELSE 2 END
    )
    SELECT s.*
    FROM reporting.vw_FinancialSummary s
    INNER JOIN LatestPeriod p
        ON p.PeriodType = s.PeriodType
       AND p.FiscalYear = s.FiscalYear
       AND p.FiscalPeriod = s.FiscalPeriod
       AND p.PeriodEnd = s.PeriodEnd;
END;
GO
