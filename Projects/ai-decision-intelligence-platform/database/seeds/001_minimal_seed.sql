SET NOCOUNT ON;
SET XACT_ABORT ON;

MERGE dbo.DimDate AS target
USING (VALUES
    (20260101, CONVERT(date,'2026-01-01'), 4, N'Thursday', 1, 1, N'January', 1, 2026, 0),
    (20260102, CONVERT(date,'2026-01-02'), 5, N'Friday',   1, 1, N'January', 1, 2026, 0),
    (20260110, CONVERT(date,'2026-01-10'), 6, N'Saturday', 2, 1, N'January', 1, 2026, 1)
) AS source (DateKey, FullDate, DayOfWeek, DayName, WeekOfYear, MonthNumber, MonthName, QuarterNumber, CalendarYear, IsWeekend)
ON target.DateKey = source.DateKey
WHEN NOT MATCHED THEN INSERT (DateKey, FullDate, DayOfWeek, DayName, WeekOfYear, MonthNumber, MonthName, QuarterNumber, CalendarYear, IsWeekend)
VALUES (source.DateKey, source.FullDate, source.DayOfWeek, source.DayName, source.WeekOfYear, source.MonthNumber, source.MonthName, source.QuarterNumber, source.CalendarYear, source.IsWeekend);

MERGE dbo.DimState AS target USING (VALUES (N'CA', N'California')) AS source (StateID, StateName)
ON target.StateID=source.StateID WHEN NOT MATCHED THEN INSERT (StateID, StateName) VALUES (source.StateID, source.StateName);

MERGE dbo.DimCategory AS target USING (VALUES (N'PHASE1_CATEGORY', N'Phase 1 Test Category', N'PHASE1_DEPT', N'Phase 1 Test Department')) AS source (CategoryID, CategoryName, DepartmentID, DepartmentName)
ON target.CategoryID=source.CategoryID WHEN NOT MATCHED THEN INSERT (CategoryID, CategoryName, DepartmentID, DepartmentName, SourceSystem) VALUES (source.CategoryID, source.CategoryName, source.DepartmentID, source.DepartmentName, N'PHASE1_SEED');

DECLARE @CategoryKey int = (SELECT CategoryKey FROM dbo.DimCategory WHERE CategoryID=N'PHASE1_CATEGORY');
DECLARE @StateKey int = (SELECT StateKey FROM dbo.DimState WHERE StateID=N'CA');

MERGE dbo.DimProduct AS target USING (VALUES (N'PHASE1_PRODUCT', N'PHASE1_ITEM', N'Phase 1 Test Product')) AS source (ProductID, ItemID, ProductName)
ON target.ProductID=source.ProductID WHEN NOT MATCHED THEN INSERT (ProductID, ItemID, CategoryKey, ProductName, UnitCost, SourceSystem) VALUES (source.ProductID, source.ItemID, @CategoryKey, source.ProductName, 2.5000, N'PHASE1_SEED');

MERGE dbo.DimStore AS target USING (VALUES (N'PHASE1_STORE', N'Phase 1 Test Store')) AS source (StoreID, StoreName)
ON target.StoreID=source.StoreID WHEN NOT MATCHED THEN INSERT (StoreID, StoreName, StateKey, SourceSystem) VALUES (source.StoreID, source.StoreName, @StateKey, N'PHASE1_SEED');

MERGE dbo.DimWarehouse AS target USING (VALUES (N'PHASE1_WH', N'Phase 1 Test Warehouse')) AS source (WarehouseID, WarehouseName)
ON target.WarehouseID=source.WarehouseID WHEN NOT MATCHED THEN INSERT (WarehouseID, WarehouseName, StateKey, CapacityUnits, CurrentUtilization, HoldingCostPerUnitDay, HandlingCostPerUnit, ServiceLevelTarget, SourceSystem) VALUES (source.WarehouseID, source.WarehouseName, @StateKey, 10000, 0.25, 0.005, 0.10, 0.95, N'PHASE1_SEED');

MERGE dbo.DimSupplier AS target USING (VALUES (N'PHASE1_SUPPLIER', N'Phase 1 Test Supplier')) AS source (SupplierID, SupplierName)
ON target.SupplierID=source.SupplierID WHEN NOT MATCHED THEN INSERT (SupplierID, SupplierName, SupplierRegion, ReliabilityScore, BaseLeadTimeDays, LeadTimeVariability, DelayProbability, MinimumOrderQuantity, MaximumOrderQuantity, DailyCapacity, PaymentTermsDays, RiskLevel, SourceSystem) VALUES (source.SupplierID, source.SupplierName, N'West', 0.95, 7, 1.5, 0.05, 10, 1000, 500, 30, N'LOW', N'PHASE1_SEED');

MERGE dbo.DimScenario AS target USING (VALUES (N'BASELINE', N'Baseline', N'BASELINE', N'none', CAST(1 AS decimal(19,6)), CAST(1 AS decimal(19,6)))) AS source (ScenarioID, ScenarioName, ScenarioType, ParameterName, BaselineValue, ScenarioValue)
ON target.ScenarioID=source.ScenarioID WHEN NOT MATCHED THEN INSERT (ScenarioID, ScenarioName, ScenarioType, ParameterName, BaselineValue, ScenarioValue, IsBaseline, SourceSystem) VALUES (source.ScenarioID, source.ScenarioName, source.ScenarioType, source.ParameterName, source.BaselineValue, source.ScenarioValue, 1, N'PHASE1_SEED');

MERGE dbo.DimModel AS target USING (VALUES
    (N'SEASONAL_NAIVE', N'Seasonal Naive', N'BASELINE', N'1.0.0'),
    (N'XGBOOST', N'XGBoost', N'GRADIENT_BOOSTING', N'1.0.0'),
    (N'LIGHTGBM', N'LightGBM', N'GRADIENT_BOOSTING', N'1.0.0')
) AS source (ModelID, ModelName, ModelType, ModelVersion)
ON target.ModelID=source.ModelID WHEN NOT MATCHED THEN INSERT (ModelID, ModelName, ModelType, ModelVersion) VALUES (source.ModelID, source.ModelName, source.ModelType, source.ModelVersion);

DECLARE @ProductKey int = (SELECT ProductKey FROM dbo.DimProduct WHERE ProductID=N'PHASE1_PRODUCT');
DECLARE @StoreKey int = (SELECT StoreKey FROM dbo.DimStore WHERE StoreID=N'PHASE1_STORE');
IF NOT EXISTS (SELECT 1 FROM dbo.FactSales WHERE DateKey=20260101 AND ProductKey=@ProductKey AND StoreKey=@StoreKey)
INSERT dbo.FactSales (DateKey, ProductKey, StoreKey, Quantity, UnitPrice, SourceSystem, DataVersion)
VALUES (20260101, @ProductKey, @StoreKey, 5, 4.99, N'PHASE1_SEED', N'phase-1');
GO
