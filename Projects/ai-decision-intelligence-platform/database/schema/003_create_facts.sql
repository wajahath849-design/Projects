SET NOCOUNT ON;
SET XACT_ABORT ON;

IF OBJECT_ID(N'dbo.FactSales', N'U') IS NULL
CREATE TABLE dbo.FactSales (
    SalesKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactSales PRIMARY KEY,
    DateKey int NOT NULL, ProductKey int NOT NULL, StoreKey int NOT NULL,
    Quantity decimal(19,4) NOT NULL, UnitPrice decimal(19,4) NULL,
    Revenue AS (Quantity * UnitPrice) PERSISTED,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_FactSales_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_FactSales_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_FactSales_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_FactSales_Quantity CHECK (Quantity >= 0),
    CONSTRAINT FK_FactSales_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_FactSales_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_FactSales_Store FOREIGN KEY (StoreKey) REFERENCES dbo.DimStore(StoreKey),
    CONSTRAINT UQ_FactSales_Grain UNIQUE (DateKey, ProductKey, StoreKey)
);

IF OBJECT_ID(N'dbo.FactSellPrice', N'U') IS NULL
CREATE TABLE dbo.FactSellPrice (
    SellPriceKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactSellPrice PRIMARY KEY,
    DateKey int NOT NULL, ProductKey int NOT NULL, StoreKey int NOT NULL,
    WeekIdentifier nvarchar(20) NOT NULL, SellPrice decimal(19,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_FactSellPrice_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_FactSellPrice_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_FactSellPrice_Source DEFAULT N'M5',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_FactSellPrice_Price CHECK (SellPrice >= 0),
    CONSTRAINT FK_FactSellPrice_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_FactSellPrice_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_FactSellPrice_Store FOREIGN KEY (StoreKey) REFERENCES dbo.DimStore(StoreKey),
    CONSTRAINT UQ_FactSellPrice_Grain UNIQUE (DateKey, ProductKey, StoreKey)
);

IF OBJECT_ID(N'dbo.FactInventorySnapshot', N'U') IS NULL
CREATE TABLE dbo.FactInventorySnapshot (
    InventorySnapshotKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactInventorySnapshot PRIMARY KEY,
    DateKey int NOT NULL, ProductKey int NOT NULL, WarehouseKey int NOT NULL,
    OpeningStock decimal(19,4) NOT NULL, ReceivedQuantity decimal(19,4) NOT NULL,
    SoldQuantity decimal(19,4) NOT NULL, DamagedQuantity decimal(19,4) NOT NULL,
    ReservedQuantityAdjustment decimal(19,4) NOT NULL, ClosingStock decimal(19,4) NOT NULL,
    LostSalesQuantity decimal(19,4) NOT NULL CONSTRAINT DF_Inventory_LostSales DEFAULT 0,
    InventoryValue decimal(19,4) NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Inventory_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Inventory_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Inventory_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_Inventory_Nonnegative CHECK (OpeningStock >= 0 AND ReceivedQuantity >= 0 AND SoldQuantity >= 0 AND DamagedQuantity >= 0 AND ClosingStock >= 0 AND LostSalesQuantity >= 0),
    CONSTRAINT CK_Inventory_Reconciliation CHECK (ClosingStock = OpeningStock + ReceivedQuantity - SoldQuantity - DamagedQuantity - ReservedQuantityAdjustment),
    CONSTRAINT FK_Inventory_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_Inventory_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT FK_Inventory_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT UQ_Inventory_Grain UNIQUE (DateKey, ProductKey, WarehouseKey)
);

IF OBJECT_ID(N'dbo.FactPurchaseOrder', N'U') IS NULL
CREATE TABLE dbo.FactPurchaseOrder (
    PurchaseOrderKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactPurchaseOrder PRIMARY KEY,
    PurchaseOrderID nvarchar(50) NOT NULL CONSTRAINT UQ_PurchaseOrder_ID UNIQUE,
    SupplierKey int NOT NULL, WarehouseKey int NOT NULL, OrderDateKey int NOT NULL,
    ExpectedDeliveryDateKey int NULL, ActualDeliveryDateKey int NULL,
    Status nvarchar(20) NOT NULL, TotalPurchaseCost decimal(19,4) NOT NULL,
    TotalTransportationCost decimal(19,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_PO_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_PO_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_PO_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_PO_Status CHECK (Status IN (N'OPEN', N'PARTIAL', N'DELAYED', N'COMPLETED', N'CANCELLED')),
    CONSTRAINT FK_PO_Supplier FOREIGN KEY (SupplierKey) REFERENCES dbo.DimSupplier(SupplierKey),
    CONSTRAINT FK_PO_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT FK_PO_OrderDate FOREIGN KEY (OrderDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_PO_ExpectedDate FOREIGN KEY (ExpectedDeliveryDateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_PO_ActualDate FOREIGN KEY (ActualDeliveryDateKey) REFERENCES dbo.DimDate(DateKey)
);

IF OBJECT_ID(N'dbo.FactPurchaseOrderLine', N'U') IS NULL
CREATE TABLE dbo.FactPurchaseOrderLine (
    PurchaseOrderLineKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactPOLine PRIMARY KEY,
    PurchaseOrderKey bigint NOT NULL, LineNumber int NOT NULL, ProductKey int NOT NULL,
    OrderedQuantity decimal(19,4) NOT NULL, ReceivedQuantity decimal(19,4) NOT NULL,
    CancelledQuantity decimal(19,4) NOT NULL, UnitCost decimal(19,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_POLine_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_POLine_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_POLine_Source DEFAULT N'SYNTHETIC',
    DataVersion nvarchar(50) NULL,
    CONSTRAINT CK_POLine_Quantity CHECK (OrderedQuantity > 0 AND ReceivedQuantity >= 0 AND CancelledQuantity >= 0 AND ReceivedQuantity + CancelledQuantity <= OrderedQuantity),
    CONSTRAINT FK_POLine_PO FOREIGN KEY (PurchaseOrderKey) REFERENCES dbo.FactPurchaseOrder(PurchaseOrderKey),
    CONSTRAINT FK_POLine_Product FOREIGN KEY (ProductKey) REFERENCES dbo.DimProduct(ProductKey),
    CONSTRAINT UQ_POLine_Grain UNIQUE (PurchaseOrderKey, LineNumber)
);

IF OBJECT_ID(N'dbo.FactSupplierPerformance', N'U') IS NULL
CREATE TABLE dbo.FactSupplierPerformance (
    SupplierPerformanceKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactSupplierPerformance PRIMARY KEY,
    DateKey int NOT NULL, SupplierKey int NOT NULL, OnTimeDeliveryRate decimal(9,6) NOT NULL,
    FillRate decimal(9,6) NOT NULL, DefectRate decimal(9,6) NOT NULL, AverageLeadTimeDays decimal(9,4) NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_SupplierPerf_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_SupplierPerf_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_SupplierPerf_Source DEFAULT N'SYNTHETIC', DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_SupplierPerf_Date FOREIGN KEY (DateKey) REFERENCES dbo.DimDate(DateKey),
    CONSTRAINT FK_SupplierPerf_Supplier FOREIGN KEY (SupplierKey) REFERENCES dbo.DimSupplier(SupplierKey),
    CONSTRAINT UQ_SupplierPerf_Grain UNIQUE (DateKey, SupplierKey)
);

IF OBJECT_ID(N'dbo.FactTransportation', N'U') IS NULL
CREATE TABLE dbo.FactTransportation (
    TransportationKey bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_FactTransportation PRIMARY KEY,
    SupplierKey int NOT NULL, WarehouseKey int NOT NULL, DistanceKM decimal(19,4) NOT NULL,
    BaseShippingCost decimal(19,4) NOT NULL, ShippingCostPerUnit decimal(19,6) NOT NULL,
    AverageTransitDays decimal(9,4) NOT NULL, TransitVariability decimal(9,4) NOT NULL,
    CarbonEmissionPerUnit decimal(19,6) NOT NULL, PreferredLaneFlag bit NOT NULL,
    CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_Transportation_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_Transportation_UpdatedAt DEFAULT SYSUTCDATETIME(),
    PipelineRunID uniqueidentifier NULL, SourceSystem nvarchar(50) NOT NULL CONSTRAINT DF_Transportation_Source DEFAULT N'SYNTHETIC', DataVersion nvarchar(50) NULL,
    CONSTRAINT FK_Transportation_Supplier FOREIGN KEY (SupplierKey) REFERENCES dbo.DimSupplier(SupplierKey),
    CONSTRAINT FK_Transportation_Warehouse FOREIGN KEY (WarehouseKey) REFERENCES dbo.DimWarehouse(WarehouseKey),
    CONSTRAINT UQ_Transportation_Lane UNIQUE (SupplierKey, WarehouseKey)
);
GO
