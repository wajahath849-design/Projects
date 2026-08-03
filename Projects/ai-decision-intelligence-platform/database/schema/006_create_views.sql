SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.vw_ExecutiveOverview AS
SELECT
    d.FullDate,
    SUM(s.Quantity) AS TotalActualDemand,
    SUM(s.Revenue) AS TotalRevenue,
    SUM(f.ForecastQuantity) AS TotalForecastDemand,
    SUM(f.ExpectedRevenue) AS ForecastRevenue
FROM dbo.DimDate d
LEFT JOIN dbo.FactSales s ON s.DateKey = d.DateKey
LEFT JOIN dbo.FactForecast f ON f.TargetDateKey = d.DateKey
GROUP BY d.FullDate;
GO

CREATE OR ALTER VIEW dbo.vw_DemandForecast AS
SELECT f.ForecastKey, fd.FullDate AS ForecastDate, td.FullDate AS TargetDate,
       p.ProductID, s.StoreID, m.ModelName, f.HorizonDays, f.ForecastQuantity,
       f.LowerBound, f.UpperBound, f.ExpectedRevenue, f.ForecastBias,
       f.ForecastConfidence, f.StockoutProbability
FROM dbo.FactForecast f
JOIN dbo.DimDate fd ON fd.DateKey = f.ForecastDateKey
JOIN dbo.DimDate td ON td.DateKey = f.TargetDateKey
JOIN dbo.DimProduct p ON p.ProductKey = f.ProductKey
LEFT JOIN dbo.DimStore s ON s.StoreKey = f.StoreKey
JOIN dbo.DimModel m ON m.ModelKey = f.ModelKey;
GO

CREATE OR ALTER VIEW dbo.vw_InventoryIntelligence AS
SELECT i.InventorySnapshotKey, d.FullDate, p.ProductID, w.WarehouseID,
       i.OpeningStock, i.ReceivedQuantity, i.SoldQuantity, i.ClosingStock,
       i.LostSalesQuantity, i.InventoryValue, r.SafetyStock, r.ReorderPoint,
       r.ProjectedInventory, r.DaysOfSupply, r.StockoutProbability,
       r.RiskClassification
FROM dbo.FactInventorySnapshot i
JOIN dbo.DimDate d ON d.DateKey = i.DateKey
JOIN dbo.DimProduct p ON p.ProductKey = i.ProductKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey = i.WarehouseKey
LEFT JOIN dbo.FactStockoutRisk r ON r.DateKey = i.DateKey
    AND r.ProductKey = i.ProductKey AND r.WarehouseKey = i.WarehouseKey;
GO

CREATE OR ALTER VIEW dbo.vw_OptimizationRecommendations AS
SELECT r.OptimizationRecommendationKey, r.RecommendationID, d.FullDate,
       p.ProductID, s.SupplierID, w.WarehouseID, r.RecommendedOrderQuantity,
       od.FullDate AS RecommendedOrderDate, ed.FullDate AS ExpectedDeliveryDate,
       r.ExpectedTotalCost, r.ExpectedRevenueProtected, r.ExpectedStockoutReduction,
       r.EstimatedFinancialImpact, r.RecommendationPriority, r.SolverStatus,
       r.DiagnosticMessage
FROM dbo.FactOptimizationRecommendation r
JOIN dbo.DimDate d ON d.DateKey = r.DateKey
JOIN dbo.DimDate od ON od.DateKey = r.RecommendedOrderDateKey
JOIN dbo.DimDate ed ON ed.DateKey = r.ExpectedDeliveryDateKey
JOIN dbo.DimProduct p ON p.ProductKey = r.ProductKey
JOIN dbo.DimSupplier s ON s.SupplierKey = r.SupplierKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey = r.WarehouseKey;
GO

CREATE OR ALTER VIEW dbo.vw_ScenarioComparison AS
SELECT sr.ScenarioResultKey, sc.ScenarioID, sc.ScenarioName, sc.ScenarioType,
       d.FullDate, p.ProductID, w.WarehouseID,
       sr.ScenarioDemand - sr.BaselineDemand AS DemandImpact,
       sr.ScenarioRevenue - sr.BaselineRevenue AS RevenueImpact,
       sr.ScenarioTotalCost - sr.BaselineTotalCost AS CostImpact,
       sr.ScenarioProfit - sr.BaselineProfit AS ProfitImpact,
       sr.ScenarioStockoutProbability - sr.BaselineStockoutProbability AS StockoutImpact,
       sr.RevenueProtected
FROM dbo.FactScenarioResult sr
JOIN dbo.DimScenario sc ON sc.ScenarioKey = sr.ScenarioKey
JOIN dbo.DimDate d ON d.DateKey = sr.DateKey
LEFT JOIN dbo.DimProduct p ON p.ProductKey = sr.ProductKey
LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey = sr.WarehouseKey;
GO

CREATE OR ALTER VIEW dbo.vw_ModelPerformance AS
SELECT fm.ForecastMetricKey, m.ModelID, m.ModelName, m.ModelVersion,
       mr.ModelRunID, mr.RunStatus, mr.TrainingTimeSeconds, mr.InferenceTimeSeconds,
       p.ProductID, c.CategoryID, fm.HorizonDays, fm.FoldNumber,
       fm.WAPE, fm.RMSE, fm.MAE, fm.Bias, fm.SMAPE, fm.MASE, fm.RMSSE, fm.Coverage
FROM dbo.FactForecastMetric fm
JOIN dbo.DimModel m ON m.ModelKey = fm.ModelKey
JOIN dbo.FactModelRun mr ON mr.ModelRunKey = fm.ModelRunKey
LEFT JOIN dbo.DimProduct p ON p.ProductKey = fm.ProductKey
LEFT JOIN dbo.DimCategory c ON c.CategoryKey = fm.CategoryKey;
GO

CREATE OR ALTER VIEW dbo.vw_DataQualitySummary AS
SELECT d.FullDate, q.TableName, q.CheckCategory, q.Severity, q.Status,
       COUNT_BIG(*) AS TotalChecks, SUM(q.RecordsChecked) AS RecordsChecked,
       SUM(q.FailedRecords) AS FailedRecords,
       CAST(100.0 * SUM(q.FailedRecords) / NULLIF(SUM(q.RecordsChecked), 0) AS decimal(9,4)) AS FailurePercentage
FROM dbo.FactDataQuality q
JOIN dbo.DimDate d ON d.DateKey = q.CheckDateKey
GROUP BY d.FullDate, q.TableName, q.CheckCategory, q.Severity, q.Status;
GO

CREATE OR ALTER VIEW dbo.vw_ProductDecisionDetail AS
SELECT p.ProductKey, p.ProductID, p.ProductName, c.CategoryID, c.CategoryName,
       r.DateKey, d.FullDate, w.WarehouseID, r.CurrentInventory, r.SafetyStock,
       r.ReorderPoint, r.ProjectedInventory, r.DaysOfSupply,
       r.StockoutProbability, r.RiskClassification,
       rec.RecommendedOrderQuantity, rec.ExpectedTotalCost,
       rec.ExpectedRevenueProtected, rec.RecommendationPriority, rec.SolverStatus
FROM dbo.DimProduct p
JOIN dbo.DimCategory c ON c.CategoryKey = p.CategoryKey
LEFT JOIN dbo.FactStockoutRisk r ON r.ProductKey = p.ProductKey
LEFT JOIN dbo.DimDate d ON d.DateKey = r.DateKey
LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey = r.WarehouseKey
LEFT JOIN dbo.FactOptimizationRecommendation rec ON rec.ProductKey = p.ProductKey
    AND rec.WarehouseKey = r.WarehouseKey AND rec.DateKey = r.DateKey;
GO
