SET NOCOUNT ON;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_ExecutiveOverview AS
WITH sales AS (
  SELECT DateKey,SUM(Quantity) TotalActualDemand,SUM(Revenue) TotalRevenue
  FROM dbo.FactSales GROUP BY DateKey
), forecast AS (
  SELECT TargetDateKey DateKey,SUM(ForecastQuantity) ExpectedDemand,
    SUM(ExpectedRevenue) ForecastRevenue
  FROM dbo.FactForecast GROUP BY TargetDateKey
), inventory AS (
  SELECT DateKey,SUM(InventoryValue) InventoryValue
  FROM dbo.FactInventorySnapshot GROUP BY DateKey
), risk AS (
  SELECT DateKey,
    SUM(CASE WHEN RiskClassification IN ('Critical','At Risk') THEN 1 ELSE 0 END) ProductsAtRisk,
    SUM(CASE WHEN RiskClassification='Critical' THEN 1 ELSE 0 END) CriticalStockouts
  FROM dbo.FactStockoutRisk GROUP BY DateKey
), recommendation AS (
  SELECT DateKey,SUM(ExpectedPurchaseCost) RecommendedPurchaseValue,
    SUM(ExpectedRevenueProtected) ExpectedRevenueProtected,
    SUM(EstimatedFinancialImpact) OptimizationSavings
  FROM dbo.FactOptimizationRecommendation GROUP BY DateKey
), keys AS (
  SELECT DateKey FROM sales UNION SELECT DateKey FROM forecast UNION SELECT DateKey FROM inventory
  UNION SELECT DateKey FROM risk UNION SELECT DateKey FROM recommendation
)
SELECT d.DateKey,d.FullDate,
  COALESCE(s.TotalActualDemand,0) TotalActualDemand,COALESCE(s.TotalRevenue,0) TotalRevenue,
  COALESCE(f.ExpectedDemand,0) ExpectedDemand,COALESCE(f.ForecastRevenue,0) ForecastRevenue,
  COALESCE(i.InventoryValue,0) InventoryValue,COALESCE(r.ProductsAtRisk,0) ProductsAtRisk,
  COALESCE(r.CriticalStockouts,0) CriticalStockouts,
  COALESCE(rec.RecommendedPurchaseValue,0) RecommendedPurchaseValue,
  COALESCE(rec.ExpectedRevenueProtected,0) ExpectedRevenueProtected,
  COALESCE(rec.OptimizationSavings,0) OptimizationSavings
FROM keys k JOIN dbo.DimDate d ON d.DateKey=k.DateKey
LEFT JOIN sales s ON s.DateKey=k.DateKey LEFT JOIN forecast f ON f.DateKey=k.DateKey
LEFT JOIN inventory i ON i.DateKey=k.DateKey LEFT JOIN risk r ON r.DateKey=k.DateKey
LEFT JOIN recommendation rec ON rec.DateKey=k.DateKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_DemandForecast AS
WITH actual AS (
  SELECT DateKey,ProductKey,StoreKey,SUM(Quantity) ActualDemand,SUM(Revenue) ActualRevenue
  FROM dbo.FactSales GROUP BY DateKey,ProductKey,StoreKey
), forecast AS (
  SELECT TargetDateKey DateKey,ProductKey,StoreKey,ModelKey,HorizonDays,
    SUM(ForecastQuantity) ForecastDemand,SUM(LowerBound) LowerBound,
    SUM(UpperBound) UpperBound,SUM(ExpectedRevenue) ForecastRevenue,
    AVG(ForecastBias) ForecastBias,AVG(ForecastConfidence) ForecastConfidence
  FROM dbo.FactForecast GROUP BY TargetDateKey,ProductKey,StoreKey,ModelKey,HorizonDays
), combined AS (
  SELECT COALESCE(a.DateKey,f.DateKey) DateKey,COALESCE(a.ProductKey,f.ProductKey) ProductKey,
    COALESCE(a.StoreKey,f.StoreKey) StoreKey,f.ModelKey,f.HorizonDays,
    a.ActualDemand,a.ActualRevenue,f.ForecastDemand,f.LowerBound,f.UpperBound,
    f.ForecastRevenue,f.ForecastBias,f.ForecastConfidence
  FROM actual a FULL OUTER JOIN forecast f ON f.DateKey=a.DateKey
    AND f.ProductKey=a.ProductKey AND f.StoreKey=a.StoreKey
)
SELECT c.DateKey,d.FullDate,c.ProductKey,p.ProductID,p.ProductName,cat.CategoryID,
  c.StoreKey,s.StoreID,st.StateID,m.ModelID,m.ModelName,c.HorizonDays,
  COALESCE(c.ActualDemand,0) ActualDemand,COALESCE(c.ActualRevenue,0) ActualRevenue,
  COALESCE(c.ForecastDemand,0) ForecastDemand,c.LowerBound,c.UpperBound,
  COALESCE(c.ForecastRevenue,0) ForecastRevenue,c.ForecastBias,c.ForecastConfidence
FROM combined c JOIN dbo.DimDate d ON d.DateKey=c.DateKey
JOIN dbo.DimProduct p ON p.ProductKey=c.ProductKey
JOIN dbo.DimCategory cat ON cat.CategoryKey=p.CategoryKey
LEFT JOIN dbo.DimStore s ON s.StoreKey=c.StoreKey LEFT JOIN dbo.DimState st ON st.StateKey=s.StateKey
LEFT JOIN dbo.DimModel m ON m.ModelKey=c.ModelKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_InventoryIntelligence AS
SELECT r.DateKey,d.FullDate,r.ProductKey,p.ProductID,p.ProductName,c.CategoryID,
  r.WarehouseKey,w.WarehouseID,w.WarehouseName,r.CurrentInventory,r.SafetyStock,
  r.ReorderPoint,r.ProjectedInventory,r.DaysOfSupply,r.StockoutProbability,
  r.RiskClassification,w.CapacityUnits,w.CurrentUtilization,
  latest.InventoryValue
FROM dbo.FactStockoutRisk r JOIN dbo.DimDate d ON d.DateKey=r.DateKey
JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey JOIN dbo.DimCategory c ON c.CategoryKey=p.CategoryKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey
LEFT JOIN dbo.FactInventorySnapshot latest ON latest.DateKey=r.DateKey
  AND latest.ProductKey=r.ProductKey AND latest.WarehouseKey=r.WarehouseKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_OptimizationRecommendations AS
SELECT r.DateKey,d.FullDate,r.RecommendationID,r.ProductKey,p.ProductID,p.ProductName,
  r.SupplierKey,s.SupplierID,s.SupplierName,s.ReliabilityScore,s.BaseLeadTimeDays,
  r.WarehouseKey,w.WarehouseID,
  r.RecommendedOrderQuantity,od.FullDate RecommendedOrderDate,
  ed.FullDate ExpectedDeliveryDate,r.ExpectedPurchaseCost,r.ExpectedTransportationCost,
  r.ExpectedHoldingCost,r.ExpectedStockoutCost,r.ExpectedTotalCost,
  r.ExpectedRevenueProtected,r.ExpectedStockoutReduction,r.EstimatedFinancialImpact,
  r.RecommendationPriority,r.SolverStatus,r.DiagnosticMessage,
  a.CapacityBefore,a.CapacityAfter,a.AllocatedQuantity,a.AllocationCost
FROM dbo.FactOptimizationRecommendation r JOIN dbo.DimDate d ON d.DateKey=r.DateKey
JOIN dbo.DimDate od ON od.DateKey=r.RecommendedOrderDateKey
JOIN dbo.DimDate ed ON ed.DateKey=r.ExpectedDeliveryDateKey
JOIN dbo.DimProduct p ON p.ProductKey=r.ProductKey
JOIN dbo.DimSupplier s ON s.SupplierKey=r.SupplierKey
JOIN dbo.DimWarehouse w ON w.WarehouseKey=r.WarehouseKey
LEFT JOIN dbo.FactOptimizationAllocation a
  ON a.OptimizationRecommendationKey=r.OptimizationRecommendationKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_ScenarioComparison AS
SELECT sr.DateKey,d.FullDate,sc.ScenarioID,sc.ScenarioName,sc.ScenarioType,
  sc.ParameterName,sc.BaselineValue,sc.ScenarioValue,p.ProductID,w.WarehouseID,
  sr.BaselineDemand,sr.ScenarioDemand,sr.BaselineRevenue,sr.ScenarioRevenue,
  sr.BaselineInventory,sr.ScenarioInventory,sr.BaselineStockoutProbability,
  sr.ScenarioStockoutProbability,sr.BaselineOrderQuantity,sr.ScenarioOrderQuantity,
  sr.BaselinePurchaseCost,sr.ScenarioPurchaseCost,
  sr.BaselineTransportationCost,sr.ScenarioTransportationCost,
  sr.BaselineHoldingCost,sr.ScenarioHoldingCost,sr.BaselineTotalCost,sr.ScenarioTotalCost,
  sr.BaselineProfit,sr.ScenarioProfit,sr.BaselineRevenueProtected,
  sr.ScenarioRevenueProtected,sr.RevenueProtected
FROM dbo.FactScenarioResult sr JOIN dbo.DimScenario sc ON sc.ScenarioKey=sr.ScenarioKey
JOIN dbo.DimDate d ON d.DateKey=sr.DateKey
LEFT JOIN dbo.DimProduct p ON p.ProductKey=sr.ProductKey
LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey=sr.WarehouseKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_ModelPerformance AS
SELECT fm.ForecastMetricKey,m.ModelID,m.ModelName,m.ModelVersion,m.IsProduction,
  mr.ModelRunID,mr.RunStatus,mr.RunStartedAt,mr.RunCompletedAt,mr.TrainingRows,
  mr.TrainingTimeSeconds,mr.InferenceTimeSeconds,p.ProductID,c.CategoryID,
  fm.HorizonDays,fm.FoldNumber,fm.WAPE,fm.RMSE,fm.MAE,fm.Bias,fm.SMAPE,
  fm.MASE,fm.RMSSE,fm.Coverage
FROM dbo.FactForecastMetric fm JOIN dbo.DimModel m ON m.ModelKey=fm.ModelKey
JOIN dbo.FactModelRun mr ON mr.ModelRunKey=fm.ModelRunKey
LEFT JOIN dbo.DimProduct p ON p.ProductKey=fm.ProductKey
LEFT JOIN dbo.DimCategory c ON c.CategoryKey=fm.CategoryKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_DataQuality AS
SELECT q.DataQualityKey,q.CheckDateKey,d.FullDate,q.TableName,q.CheckName,q.CheckCategory,
  q.Severity,q.Status,q.RecordsChecked,q.FailedRecords,q.FailurePercentage,
  q.CreatedAt,q.PipelineRunID,q.SourceSystem,q.DataVersion
FROM dbo.FactDataQuality q JOIN dbo.DimDate d ON d.DateKey=q.CheckDateKey;
GO

CREATE OR ALTER VIEW dbo.vw_PBI_ForecastExplanations AS
SELECT f.ForecastID,td.FullDate TargetDate,p.ProductID,s.StoreID,m.ModelName,
  e.FeatureName,e.FeatureValue,e.ShapValue,ABS(e.ShapValue) AbsoluteImpact,
  e.Direction,e.ContributionRank,e.ExplanationText
FROM dbo.FactModelExplanation e JOIN dbo.FactForecast f ON f.ForecastKey=e.ForecastKey
JOIN dbo.DimDate td ON td.DateKey=f.TargetDateKey
JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
LEFT JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
JOIN dbo.DimModel m ON m.ModelKey=f.ModelKey;
GO
