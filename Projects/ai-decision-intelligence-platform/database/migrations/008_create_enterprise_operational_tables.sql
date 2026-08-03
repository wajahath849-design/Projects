SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.BridgeSupplierProduct', N'U') IS NULL
CREATE TABLE dbo.BridgeSupplierProduct (
    SupplierProductKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_BridgeSupplierProduct PRIMARY KEY,
    SupplierKey int NOT NULL, ProductKey int NOT NULL,
    PurchaseCost decimal(19,4) NOT NULL, MinimumOrderQuantity decimal(19,4) NOT NULL,
    MaximumOrderQuantity decimal(19,4) NOT NULL, DailyCapacity decimal(19,4) NOT NULL,
    LeadTimeDays smallint NOT NULL, PreferredSupplierFlag bit NOT NULL,
    ActiveFlag bit NOT NULL CONSTRAINT DF_SupplierProduct_Active DEFAULT 1,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_SupplierProduct_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_SupplierProduct_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL,
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_SupplierProduct_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_SupplierProduct_Quantity CHECK (
        PurchaseCost >= 0 AND MinimumOrderQuantity > 0
        AND MaximumOrderQuantity >= MinimumOrderQuantity
        AND DailyCapacity >= MinimumOrderQuantity
    ),
    CONSTRAINT FK_SupplierProduct_Supplier FOREIGN KEY (SupplierKey) REFERENCES dbo.DimSupplier(SupplierKey),
    CONSTRAINT FK_SupplierProduct_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT UQ_BridgeSupplierProduct UNIQUE (SupplierKey, ProductKey)
);

IF OBJECT_ID(N'dbo.BusinessConstraint', N'U') IS NULL
CREATE TABLE dbo.BusinessConstraint (
    BusinessConstraintKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_BusinessConstraint PRIMARY KEY,
    ConstraintID nvarchar(100) NOT NULL CONSTRAINT UQ_BusinessConstraint_ID UNIQUE,
    ConstraintType nvarchar(50) NOT NULL, ScopeType nvarchar(30) NOT NULL,
    ScopeID nvarchar(100) NULL, ParameterName nvarchar(100) NOT NULL,
    ParameterValue decimal(19,6) NOT NULL, UnitOfMeasure nvarchar(30) NOT NULL,
    EffectiveDateKey int NOT NULL, ExpirationDateKey int NULL, ActiveFlag bit NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_BusinessConstraint_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_BusinessConstraint_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL,
    SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_BusinessConstraint_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_BusinessConstraint_EffectiveDate FOREIGN KEY (EffectiveDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_BusinessConstraint_ExpirationDate FOREIGN KEY (ExpirationDateKey) REFERENCES dbo.DimDate(DateKey)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'IX_SupplierProduct_ProductPreferred' AND object_id=OBJECT_ID(N'dbo.BridgeSupplierProduct'))
CREATE INDEX IX_SupplierProduct_ProductPreferred
ON dbo.BridgeSupplierProduct(ProductKey, PreferredSupplierFlag)
INCLUDE (SupplierKey, PurchaseCost, LeadTimeDays, DailyCapacity);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name=N'IX_BusinessConstraint_TypeScope' AND object_id=OBJECT_ID(N'dbo.BusinessConstraint'))
CREATE INDEX IX_BusinessConstraint_TypeScope
ON dbo.BusinessConstraint(ConstraintType, ScopeType, ScopeID, ActiveFlag)
INCLUDE (ParameterName, ParameterValue);
GO
