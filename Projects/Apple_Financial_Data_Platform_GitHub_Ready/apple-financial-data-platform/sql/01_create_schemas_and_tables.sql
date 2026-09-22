SET NOCOUNT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'finance')
    EXEC('CREATE SCHEMA finance');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'audit')
    EXEC('CREATE SCHEMA audit');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stage')
    EXEC('CREATE SCHEMA stage');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'reporting')
    EXEC('CREATE SCHEMA reporting');
GO

IF OBJECT_ID('finance.Company', 'U') IS NULL
BEGIN
    CREATE TABLE finance.Company (
        CompanyId INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Company PRIMARY KEY,
        CIK VARCHAR(10) NOT NULL CONSTRAINT UQ_Company_CIK UNIQUE,
        CompanyName NVARCHAR(200) NOT NULL,
        Ticker VARCHAR(20) NOT NULL,
        CreatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_Company_Created DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_Company_Updated DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('finance.Metric', 'U') IS NULL
BEGIN
    CREATE TABLE finance.Metric (
        MetricId INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Metric PRIMARY KEY,
        MetricCode VARCHAR(60) NOT NULL CONSTRAINT UQ_Metric_Code UNIQUE,
        MetricName NVARCHAR(200) NOT NULL,
        StatementName NVARCHAR(100) NOT NULL,
        CategoryName NVARCHAR(100) NOT NULL,
        DefaultUnit VARCHAR(30) NOT NULL,
        CreatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_Metric_Created DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_Metric_Updated DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('audit.ETLRun', 'U') IS NULL
BEGIN
    CREATE TABLE audit.ETLRun (
        RunId UNIQUEIDENTIFIER NOT NULL CONSTRAINT PK_ETLRun PRIMARY KEY,
        PipelineName VARCHAR(100) NOT NULL,
        SourceSystem VARCHAR(100) NOT NULL,
        SourceUrl NVARCHAR(1000) NULL,
        Status VARCHAR(30) NOT NULL,
        SourceRecordCount INT NULL,
        LoadedRecordCount INT NULL,
        ErrorCount INT NULL,
        WarningCount INT NULL,
        Message NVARCHAR(1000) NULL,
        StartedAtUtc DATETIME2(0) NOT NULL,
        FinishedAtUtc DATETIME2(0) NULL
    );
END;
GO

IF OBJECT_ID('finance.FinancialFact', 'U') IS NULL
BEGIN
    CREATE TABLE finance.FinancialFact (
        FinancialFactId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FinancialFact PRIMARY KEY,
        BusinessKey CHAR(64) NOT NULL CONSTRAINT UQ_FinancialFact_BusinessKey UNIQUE,
        CompanyId INT NOT NULL,
        MetricId INT NOT NULL,
        Taxonomy VARCHAR(50) NOT NULL,
        SourceTag VARCHAR(200) NOT NULL,
        Unit VARCHAR(30) NOT NULL,
        FactValue DECIMAL(28,4) NOT NULL,
        PeriodStart DATE NULL,
        PeriodEnd DATE NOT NULL,
        DurationDays INT NULL,
        PeriodType VARCHAR(20) NOT NULL,
        FiscalYear INT NOT NULL,
        FiscalPeriod VARCHAR(10) NOT NULL,
        FormType VARCHAR(10) NOT NULL,
        FiledDate DATE NOT NULL,
        AccessionNumber VARCHAR(30) NOT NULL,
        SourceUrl NVARCHAR(1000) NULL,
        IsDerived BIT NOT NULL CONSTRAINT DF_FinancialFact_IsDerived DEFAULT 0,
        DerivationMethod NVARCHAR(300) NULL,
        LastRunId UNIQUEIDENTIFIER NOT NULL,
        CreatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_FinancialFact_Created DEFAULT SYSUTCDATETIME(),
        UpdatedAtUtc DATETIME2(0) NOT NULL CONSTRAINT DF_FinancialFact_Updated DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_FinancialFact_Company FOREIGN KEY (CompanyId) REFERENCES finance.Company(CompanyId),
        CONSTRAINT FK_FinancialFact_Metric FOREIGN KEY (MetricId) REFERENCES finance.Metric(MetricId),
        CONSTRAINT FK_FinancialFact_Run FOREIGN KEY (LastRunId) REFERENCES audit.ETLRun(RunId),
        CONSTRAINT CK_FinancialFact_PeriodType CHECK (PeriodType IN ('Annual', 'Quarterly')),
        CONSTRAINT CK_FinancialFact_FiscalPeriod CHECK (FiscalPeriod IN ('FY', 'Q1', 'Q2', 'Q3', 'Q4'))
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_FinancialFact_Reporting' AND object_id = OBJECT_ID('finance.FinancialFact')
)
BEGIN
    CREATE INDEX IX_FinancialFact_Reporting
        ON finance.FinancialFact (CompanyId, FiscalYear, FiscalPeriod, PeriodType)
        INCLUDE (MetricId, FactValue, PeriodEnd, Unit, FiledDate, IsDerived);
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_FinancialFact_MetricPeriod' AND object_id = OBJECT_ID('finance.FinancialFact')
)
BEGIN
    CREATE INDEX IX_FinancialFact_MetricPeriod
        ON finance.FinancialFact (MetricId, PeriodEnd, PeriodType)
        INCLUDE (FactValue, FiscalYear, FiscalPeriod, CompanyId);
END;
GO

IF OBJECT_ID('audit.DataQualityIssue', 'U') IS NULL
BEGIN
    CREATE TABLE audit.DataQualityIssue (
        IssueId BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DataQualityIssue PRIMARY KEY,
        RunId UNIQUEIDENTIFIER NOT NULL,
        Severity VARCHAR(20) NOT NULL,
        CheckName VARCHAR(100) NOT NULL,
        MetricCode VARCHAR(60) NULL,
        FiscalYear INT NULL,
        FiscalPeriod VARCHAR(10) NULL,
        PeriodEnd DATE NULL,
        IssueDetails NVARCHAR(1000) NOT NULL,
        DetectedAtUtc DATETIME2(0) NOT NULL,
        CONSTRAINT FK_DataQualityIssue_Run FOREIGN KEY (RunId) REFERENCES audit.ETLRun(RunId),
        CONSTRAINT CK_DataQualityIssue_Severity CHECK (Severity IN ('ERROR', 'WARNING', 'INFO'))
    );
END;
GO

IF OBJECT_ID('stage.FinancialFactStage', 'U') IS NULL
BEGIN
    CREATE TABLE stage.FinancialFactStage (
        company_cik VARCHAR(10) NOT NULL,
        metric_code VARCHAR(60) NOT NULL,
        metric_name NVARCHAR(200) NOT NULL,
        statement_name NVARCHAR(100) NOT NULL,
        category_name NVARCHAR(100) NOT NULL,
        taxonomy VARCHAR(50) NOT NULL,
        source_tag VARCHAR(200) NOT NULL,
        unit VARCHAR(30) NOT NULL,
        value DECIMAL(28,4) NOT NULL,
        period_start DATE NULL,
        period_end DATE NOT NULL,
        duration_days INT NULL,
        period_type VARCHAR(20) NOT NULL,
        fiscal_year INT NOT NULL,
        fiscal_period VARCHAR(10) NOT NULL,
        form_type VARCHAR(10) NOT NULL,
        filed_date DATE NOT NULL,
        accession_number VARCHAR(30) NOT NULL,
        source_url NVARCHAR(1000) NULL,
        is_derived BIT NOT NULL,
        derivation_method NVARCHAR(300) NULL,
        business_key CHAR(64) NOT NULL,
        run_id UNIQUEIDENTIFIER NOT NULL
    );
END;
GO
