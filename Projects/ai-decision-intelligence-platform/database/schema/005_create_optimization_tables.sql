SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.FactOptimizationRecommendation', N'U') IS NULL
CREATE TABLE dbo.FactOptimizationRecommendation (
    OptimizationRecommendationKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_OptimizationRecommendation PRIMARY KEY,
    RecommendationID uniqueidentifier NOT NULL CONSTRAINT UQ_Recommendation_ID UNIQUE,
    DateKey int NOT NULL, ProductKey int NOT NULL, SupplierKey int NOT NULL, WarehouseKey int NOT NULL,
    ForecastKey bigint NULL, ScenarioKey int NULL, RecommendedOrderQuantity decimal(19,6) NOT NULL,
    RecommendedOrderDateKey int NOT NULL, ExpectedDeliveryDateKey int NOT NULL,
    SafetyStock decimal(19,6) NOT NULL, ExpectedInventoryAfterReplenishment decimal(19,6) NOT NULL,
    ExpectedPurchaseCost decimal(19,4) NOT NULL, ExpectedTransportationCost decimal(19,4) NOT NULL,
    ExpectedHoldingCost decimal(19,4) NOT NULL, ExpectedStockoutCost decimal(19,4) NOT NULL,
    ExpectedTotalCost decimal(19,4) NOT NULL, ExpectedRevenueProtected decimal(19,4) NOT NULL,
    ExpectedStockoutReduction decimal(9,6) NOT NULL, EstimatedFinancialImpact decimal(19,4) NOT NULL,
    RecommendationPriority nvarchar(20) NOT NULL, SolverStatus nvarchar(20) NOT NULL,
    DiagnosticMessage nvarchar(2000) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Recommendation_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Recommendation_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Recommendation_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_Recommendation_Quantity CHECK (RecommendedOrderQuantity >= 0),
    CONSTRAINT CK_Recommendation_Status CHECK (SolverStatus IN (N'OPTIMAL', N'FEASIBLE', N'INFEASIBLE', N'UNBOUNDED', N'ERROR')),
    CONSTRAINT FK_Recommendation_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_Recommendation_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_Recommendation_Supplier FOREIGN KEY (SupplierKey) REFERENCES dbo.DimSupplier(SupplierKey),
    CONSTRAINT FK_Recommendation_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT FK_Recommendation_Forecast FOREIGN KEY (ForecastKey) REFERENCES dbo.FactForecast(ForecastKey),
    CONSTRAINT FK_Recommendation_Scenario FOREIGN KEY (ScenarioKey) REFERENCES dbo.DimScenario(ScenarioKey),
    CONSTRAINT FK_Recommendation_OrderDate FOREIGN KEY (RecommendedOrderDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_Recommendation_DeliveryDate FOREIGN KEY (ExpectedDeliveryDateKey) REFERENCES dbo.DimDate(DateKey)
);

IF OBJECT_ID(N'dbo.FactOptimizationAllocation', N'U') IS NULL
CREATE TABLE dbo.FactOptimizationAllocation (
    OptimizationAllocationKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_OptimizationAllocation PRIMARY KEY,
    OptimizationRecommendationKey bigint NOT NULL, WarehouseKey int NOT NULL,
    AllocatedQuantity decimal(19,6) NOT NULL, CapacityBefore decimal(19,6) NOT NULL,
    CapacityAfter decimal(19,6) NOT NULL, AllocationCost decimal(19,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Allocation_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Allocation_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Allocation_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_Allocation_Quantity CHECK (AllocatedQuantity >= 0 AND CapacityAfter >= 0),
    CONSTRAINT FK_Allocation_Recommendation FOREIGN KEY (OptimizationRecommendationKey) REFERENCES dbo.FactOptimizationRecommendation(OptimizationRecommendationKey),
    CONSTRAINT FK_Allocation_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey)
);

IF OBJECT_ID(N'dbo.FactScenarioResult', N'U') IS NULL
CREATE TABLE dbo.FactScenarioResult (
    ScenarioResultKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactScenarioResult PRIMARY KEY,
    ScenarioKey int NOT NULL, DateKey int NOT NULL, ProductKey int NULL, WarehouseKey int NULL,
    BaselineDemand decimal(19,6) NOT NULL, ScenarioDemand decimal(19,6) NOT NULL,
    BaselineRevenue decimal(19,4) NOT NULL, ScenarioRevenue decimal(19,4) NOT NULL,
    BaselineInventory decimal(19,6) NOT NULL, ScenarioInventory decimal(19,6) NOT NULL,
    BaselineStockoutProbability decimal(9,6) NOT NULL, ScenarioStockoutProbability decimal(9,6) NOT NULL,
    BaselineOrderQuantity decimal(19,6) NOT NULL, ScenarioOrderQuantity decimal(19,6) NOT NULL,
    BaselinePurchaseCost decimal(19,4) NULL, ScenarioPurchaseCost decimal(19,4) NULL,
    BaselineTransportationCost decimal(19,4) NULL, ScenarioTransportationCost decimal(19,4) NULL,
    BaselineHoldingCost decimal(19,4) NULL, ScenarioHoldingCost decimal(19,4) NULL,
    BaselineTotalCost decimal(19,4) NOT NULL, ScenarioTotalCost decimal(19,4) NOT NULL,
    BaselineProfit decimal(19,4) NOT NULL, ScenarioProfit decimal(19,4) NOT NULL,
    BaselineRevenueProtected decimal(19,4) NULL, ScenarioRevenueProtected decimal(19,4) NULL,
    RevenueProtected decimal(19,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_ScenarioResult_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_ScenarioResult_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_ScenarioResult_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_ScenarioResult_Scenario FOREIGN KEY (ScenarioKey) REFERENCES dbo.DimScenario(ScenarioKey),
    CONSTRAINT FK_ScenarioResult_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_ScenarioResult_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_ScenarioResult_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey)
);

IF OBJECT_ID(N'dbo.FactDataQuality', N'U') IS NULL
CREATE TABLE dbo.FactDataQuality (
    DataQualityKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactDataQuality PRIMARY KEY,
    CheckID uniqueidentifier NOT NULL CONSTRAINT UQ_DataQuality_CheckID UNIQUE,
    CheckDateKey int NOT NULL, TableName sysname NOT NULL, CheckName nvarchar(150) NOT NULL,
    CheckCategory nvarchar(50) NOT NULL, Severity nvarchar(20) NOT NULL,
    Status nvarchar(20) NOT NULL, RecordsChecked bigint NOT NULL, FailedRecords bigint NOT NULL,
    FailurePercentage decimal(9,6) NOT NULL, DetailsJson nvarchar(max) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DataQuality_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DataQuality_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DataQuality_Source DEFAULT N'PLATFORM', DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_DataQuality_Status CHECK (Status IN (N'PASS', N'WARNING', N'FAIL')),
    CONSTRAINT CK_DataQuality_Counts CHECK (RecordsChecked >= 0 AND FailedRecords >= 0 AND FailedRecords <= RecordsChecked),
    CONSTRAINT FK_DataQuality_Date FOREIGN KEY (CheckDateKey) REFERENCES dbo.DimDate(DateKey)
);
GO
