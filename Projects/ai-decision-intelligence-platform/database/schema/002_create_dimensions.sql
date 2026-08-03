SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.DimDate', N'U') IS NULL
CREATE TABLE dbo.DimDate (
    DateKey int NOT NULL CONSTRAINT PK_DimDate PRIMARY KEY,
    FullDate date NOT NULL CONSTRAINT UQ_DimDate_FullDate UNIQUE,
    DayOfWeek tinyint NOT NULL, DayName nvarchar(10) NOT NULL,
    WeekOfYear tinyint NOT NULL, MonthNumber tinyint NOT NULL,
    MonthName nvarchar(10) NOT NULL, QuarterNumber tinyint NOT NULL,
    CalendarYear smallint NOT NULL, IsWeekend bit NOT NULL,
    EventName nvarchar(100) NULL, EventType nvarchar(50) NULL,
    SnapCA bit NOT NULL CONSTRAINT DF_DimDate_SnapCA DEFAULT 0,
    SnapTX bit NOT NULL CONSTRAINT DF_DimDate_SnapTX DEFAULT 0,
    SnapWI bit NOT NULL CONSTRAINT DF_DimDate_SnapWI DEFAULT 0,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimDate_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimDate_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimDate_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL
);

IF OBJECT_ID(N'dbo.DimState', N'U') IS NULL
CREATE TABLE dbo.DimState (
    StateKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimState PRIMARY KEY,
    StateID nvarchar(20) NOT NULL CONSTRAINT UQ_DimState_StateID UNIQUE,
    StateName nvarchar(100) NOT NULL, CountryCode char(2) NOT NULL CONSTRAINT DF_DimState_Country DEFAULT 'US',
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimState_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimState_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimState_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL
);

IF OBJECT_ID(N'dbo.DimCategory', N'U') IS NULL
CREATE TABLE dbo.DimCategory (
    CategoryKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimCategory PRIMARY KEY,
    CategoryID nvarchar(50) NOT NULL CONSTRAINT UQ_DimCategory_CategoryID UNIQUE,
    CategoryName nvarchar(100) NOT NULL, DepartmentID nvarchar(50) NULL,
    DepartmentName nvarchar(100) NULL, ActiveFlag bit NOT NULL CONSTRAINT DF_DimCategory_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimCategory_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimCategory_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimCategory_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL
);

IF OBJECT_ID(N'dbo.DimProduct', N'U') IS NULL
CREATE TABLE dbo.DimProduct (
    ProductKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimProduct PRIMARY KEY,
    ProductID nvarchar(100) NOT NULL CONSTRAINT UQ_DimProduct_ProductID UNIQUE,
    ItemID nvarchar(100) NOT NULL, CategoryKey int NOT NULL,
    ProductName nvarchar(200) NULL, UnitOfMeasure nvarchar(20) NOT NULL CONSTRAINT DF_DimProduct_Uom DEFAULT N'unit',
    UnitCost decimal(19,4) NULL, ActiveFlag bit NOT NULL CONSTRAINT DF_DimProduct_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimProduct_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimProduct_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimProduct_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_DimProduct_DimCategory FOREIGN KEY (CategoryKey) REFERENCES dbo.DimCategory(CategoryKey)
);

IF OBJECT_ID(N'dbo.DimStore', N'U') IS NULL
CREATE TABLE dbo.DimStore (
    StoreKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimStore PRIMARY KEY,
    StoreID nvarchar(50) NOT NULL CONSTRAINT UQ_DimStore_StoreID UNIQUE,
    StoreName nvarchar(100) NULL, StateKey int NOT NULL,
    ActiveFlag bit NOT NULL CONSTRAINT DF_DimStore_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimStore_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimStore_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimStore_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_DimStore_DimState FOREIGN KEY (StateKey) REFERENCES dbo.DimState(StateKey)
);

IF OBJECT_ID(N'dbo.DimWarehouse', N'U') IS NULL
CREATE TABLE dbo.DimWarehouse (
    WarehouseKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimWarehouse PRIMARY KEY,
    WarehouseID nvarchar(50) NOT NULL CONSTRAINT UQ_DimWarehouse_WarehouseID UNIQUE,
    WarehouseName nvarchar(100) NOT NULL, StateKey int NOT NULL,
    CapacityUnits decimal(19,4) NOT NULL, CurrentUtilization decimal(9,6) NOT NULL,
    HoldingCostPerUnitDay decimal(19,6) NOT NULL, HandlingCostPerUnit decimal(19,4) NOT NULL,
    ServiceLevelTarget decimal(9,6) NOT NULL, ActiveFlag bit NOT NULL CONSTRAINT DF_DimWarehouse_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimWarehouse_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimWarehouse_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimWarehouse_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_DimWarehouse_Utilization CHECK (CurrentUtilization BETWEEN 0 AND 1),
    CONSTRAINT CK_DimWarehouse_ServiceLevel CHECK (ServiceLevelTarget BETWEEN 0 AND 1),
    CONSTRAINT FK_DimWarehouse_DimState FOREIGN KEY (StateKey) REFERENCES dbo.DimState(StateKey)
);

IF OBJECT_ID(N'dbo.DimSupplier', N'U') IS NULL
CREATE TABLE dbo.DimSupplier (
    SupplierKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimSupplier PRIMARY KEY,
    SupplierID nvarchar(50) NOT NULL CONSTRAINT UQ_DimSupplier_SupplierID UNIQUE,
    SupplierName nvarchar(150) NOT NULL, SupplierRegion nvarchar(100) NOT NULL,
    ReliabilityScore decimal(9,6) NOT NULL, BaseLeadTimeDays smallint NOT NULL,
    LeadTimeVariability decimal(9,4) NOT NULL, DelayProbability decimal(9,6) NOT NULL,
    MinimumOrderQuantity decimal(19,4) NOT NULL, MaximumOrderQuantity decimal(19,4) NOT NULL,
    DailyCapacity decimal(19,4) NOT NULL, PaymentTermsDays smallint NOT NULL,
    RiskLevel nvarchar(20) NOT NULL, ActiveFlag bit NOT NULL CONSTRAINT DF_DimSupplier_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimSupplier_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimSupplier_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimSupplier_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_DimSupplier_Reliability CHECK (ReliabilityScore BETWEEN 0 AND 1),
    CONSTRAINT CK_DimSupplier_Quantity CHECK (MinimumOrderQuantity >= 0 AND MaximumOrderQuantity >= MinimumOrderQuantity)
);

IF OBJECT_ID(N'dbo.DimScenario', N'U') IS NULL
CREATE TABLE dbo.DimScenario (
    ScenarioKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimScenario PRIMARY KEY,
    ScenarioID nvarchar(50) NOT NULL CONSTRAINT UQ_DimScenario_ScenarioID UNIQUE,
    ScenarioName nvarchar(150) NOT NULL, ScenarioType nvarchar(50) NOT NULL,
    ParameterName nvarchar(100) NOT NULL, BaselineValue decimal(19,6) NOT NULL,
    ScenarioValue decimal(19,6) NOT NULL, IsBaseline bit NOT NULL CONSTRAINT DF_DimScenario_Baseline DEFAULT 0,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimScenario_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimScenario_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimScenario_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL
);

IF OBJECT_ID(N'dbo.DimModel', N'U') IS NULL
CREATE TABLE dbo.DimModel (
    ModelKey int IDENTITY(1,1) NOT NULL CONSTRAINT PK_DimModel PRIMARY KEY,
    ModelID nvarchar(50) NOT NULL CONSTRAINT UQ_DimModel_ModelID UNIQUE,
    ModelName nvarchar(100) NOT NULL, ModelType nvarchar(50) NOT NULL,
    ModelVersion nvarchar(50) NOT NULL, IsProduction bit NOT NULL CONSTRAINT DF_DimModel_Production DEFAULT 0,
    ActiveFlag bit NOT NULL CONSTRAINT DF_DimModel_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimModel_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_DimModel_UpdatedAt DEFAULT SYSUTCDATETIME(),
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_DimModel_Source DEFAULT N'PLATFORM',
    DataVersion nvarchar(50) NULL
);
GO
