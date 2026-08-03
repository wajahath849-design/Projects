SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.FactModelRun', N'U') IS NULL
CREATE TABLE dbo.FactModelRun (
    ModelRunKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactModelRun PRIMARY KEY,
    ModelRunID uniqueidentifier NOT NULL CONSTRAINT UQ_ModelRun_ID UNIQUE,
    ModelKey int NOT NULL, RunStartedAt datetime2(3) NOT NULL, RunCompletedAt datetime2(3) NULL,
    RunStatus nvarchar(20) NOT NULL, ParametersJson nvarchar(max) NULL,
    TrainingRows bigint NULL, TrainingTimeSeconds decimal(19,6) NULL, InferenceTimeSeconds decimal(19,6) NULL,
    ArtifactPath nvarchar(500) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_ModelRun_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_ModelRun_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_ModelRun_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_ModelRun_Status CHECK (RunStatus IN (N'STARTED', N'SUCCEEDED', N'FAILED')),
    CONSTRAINT FK_ModelRun_Model FOREIGN KEY (ModelKey) REFERENCES dbo.DimModel(ModelKey)
);

IF OBJECT_ID(N'dbo.FactForecast', N'U') IS NULL
CREATE TABLE dbo.FactForecast (
    ForecastKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactForecast PRIMARY KEY,
    ForecastID uniqueidentifier NOT NULL CONSTRAINT UQ_Forecast_ID UNIQUE,
    ForecastDateKey int NOT NULL, TargetDateKey int NOT NULL, ProductKey int NOT NULL,
    StoreKey int NULL, WarehouseKey int NULL, ModelKey int NOT NULL, ModelRunKey bigint NOT NULL,
    HorizonDays smallint NOT NULL, ForecastQuantity decimal(19,6) NOT NULL,
    LowerBound decimal(19,6) NULL, UpperBound decimal(19,6) NULL,
    ExpectedRevenue decimal(19,4) NULL, ForecastBias decimal(19,6) NULL,
    ForecastConfidence decimal(9,6) NULL,
    StockoutProbability decimal(9,6) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Forecast_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Forecast_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Forecast_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_Forecast_Values CHECK (ForecastQuantity >= 0 AND (LowerBound IS NULL OR LowerBound >= 0) AND (ForecastConfidence IS NULL OR ForecastConfidence BETWEEN 0 AND 1) AND (StockoutProbability IS NULL OR StockoutProbability BETWEEN 0 AND 1)),
    CONSTRAINT FK_Forecast_ForecastDate FOREIGN KEY (ForecastDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_Forecast_TargetDate FOREIGN KEY (TargetDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_Forecast_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_Forecast_Store FOREIGN KEY (StoreKey) REFERENCES dbo.DimStore(StoreKey),
    CONSTRAINT FK_Forecast_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT FK_Forecast_Model FOREIGN KEY (ModelKey) REFERENCES dbo.DimModel(ModelKey),
    CONSTRAINT FK_Forecast_ModelRun FOREIGN KEY (ModelRunKey) REFERENCES dbo.FactModelRun(ModelRunKey)
);

IF OBJECT_ID(N'dbo.FactForecastMetric', N'U') IS NULL
CREATE TABLE dbo.FactForecastMetric (
    ForecastMetricKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactForecastMetric PRIMARY KEY,
    ModelRunKey bigint NOT NULL, ModelKey int NOT NULL, ProductKey int NULL,
    CategoryKey int NULL, HorizonDays smallint NOT NULL, FoldNumber smallint NULL,
    WAPE decimal(19,8) NULL, RMSE decimal(19,8) NULL, MAE decimal(19,8) NULL,
    Bias decimal(19,8) NULL, SMAPE decimal(19,8) NULL,
    MASE decimal(19,8) NULL, RMSSE decimal(19,8) NULL,
    Coverage decimal(9,6) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_ForecastMetric_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_ForecastMetric_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_ForecastMetric_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_ForecastMetric_Run FOREIGN KEY (ModelRunKey) REFERENCES dbo.FactModelRun(ModelRunKey),
    CONSTRAINT FK_ForecastMetric_Model FOREIGN KEY (ModelKey) REFERENCES dbo.DimModel(ModelKey),
    CONSTRAINT FK_ForecastMetric_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_ForecastMetric_Category FOREIGN KEY (CategoryKey) REFERENCES dbo.DimCategory(CategoryKey)
);

IF OBJECT_ID(N'dbo.FactModelExplanation', N'U') IS NULL
CREATE TABLE dbo.FactModelExplanation (
    ModelExplanationKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactModelExplanation PRIMARY KEY,
    ForecastKey bigint NOT NULL, FeatureName nvarchar(150) NOT NULL,
    FeatureValue nvarchar(200) NULL, ShapValue decimal(19,8) NOT NULL,
    ContributionRank int NOT NULL, Direction nvarchar(10) NOT NULL, ExplanationText nvarchar(1000) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Explanation_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Explanation_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Explanation_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_Explanation_Direction CHECK (Direction IN (N'POSITIVE', N'NEGATIVE', N'NEUTRAL')),
    CONSTRAINT FK_Explanation_Forecast FOREIGN KEY (ForecastKey) REFERENCES dbo.FactForecast(ForecastKey),
    CONSTRAINT UQ_Explanation_Rank UNIQUE (ForecastKey, ContributionRank)
);

IF OBJECT_ID(N'dbo.FactStockoutRisk', N'U') IS NULL
CREATE TABLE dbo.FactStockoutRisk (
    StockoutRiskKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactStockoutRisk PRIMARY KEY,
    DateKey int NOT NULL, ProductKey int NOT NULL, WarehouseKey int NOT NULL,
    ForecastKey bigint NULL, CurrentInventory decimal(19,4) NOT NULL,
    SafetyStock decimal(19,4) NOT NULL, ReorderPoint decimal(19,4) NOT NULL,
    ProjectedInventory decimal(19,4) NULL,
    DaysOfSupply decimal(19,6) NULL, StockoutProbability decimal(9,6) NOT NULL,
    RiskClassification nvarchar(20) NOT NULL, ProjectedStockoutDateKey int NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_StockoutRisk_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_StockoutRisk_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_StockoutRisk_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_StockoutRisk_Probability CHECK (StockoutProbability BETWEEN 0 AND 1),
    CONSTRAINT FK_StockoutRisk_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_StockoutRisk_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_StockoutRisk_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT FK_StockoutRisk_Forecast FOREIGN KEY (ForecastKey) REFERENCES dbo.FactForecast(ForecastKey),
    CONSTRAINT FK_StockoutRisk_ProjectedDate FOREIGN KEY (ProjectedStockoutDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT UQ_StockoutRisk_Grain UNIQUE (DateKey, ProductKey, WarehouseKey)
);
GO
