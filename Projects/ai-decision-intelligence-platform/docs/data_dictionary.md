# Data dictionary

All timestamps are UTC unless they represent a business date. Monetary columns use decimal
types in SQL Server. `SourceSystem`, `DataVersion`, and pipeline IDs preserve provenance.

| Object | Grain | Important fields |
|---|---|---|
| DimDate | One calendar date | DateKey, FullDate, event, SNAP, calendar attributes |
| DimProduct | One product | ProductID, ItemID, CategoryKey, UnitCost |
| DimCategory | One category | CategoryID, department attributes |
| DimStore | One store | StoreID, StateKey |
| DimState | One state | StateID, CountryCode |
| DimWarehouse | One warehouse | capacity, utilization, holding cost, service target |
| DimSupplier | One supplier | reliability, lead time, delay probability, capacity, MOQ |
| DimScenario | One scenario definition | type, parameter, baseline and scenario values |
| DimModel | One model/version | type, version, production and active flags |
| FactSales | Product-store-date | quantity, revenue, average price |
| FactSellPrice | Product-store-date | sell price, WM year/week |
| FactInventorySnapshot | Product-warehouse-date | opening/closing stock, receipts, sales, damage, value |
| FactPurchaseOrder | One supplier-warehouse PO | dates, lifecycle status, purchase and transport totals |
| FactPurchaseOrderLine | One PO product line | ordered, received, cancelled quantities, unit cost |
| FactSupplierPerformance | Supplier-date | fill rate, on-time rate, lead time, defects |
| FactTransportation | Supplier-warehouse lane | distance, fixed/unit shipping cost, transit time |
| BridgeSupplierProduct | Eligible supplier-product | purchase cost, MOQ/max, capacity, lead time, preference |
| BusinessConstraint | One configured constraint | type, scope, parameter, value, effective dates |
| FactModelRun | One training run | parameters, rows, timings, artifact, status |
| FactForecastMetric | Model-run/fold/horizon | WAPE, RMSE, MAE, bias, sMAPE, coverage |
| FactForecast | Product-store-target-date | prediction, interval, confidence, revenue, stockout risk |
| FactModelExplanation | Forecast-feature-rank | feature value, SHAP contribution, direction, text |
| FactStockoutRisk | Product-warehouse-risk-date | current/projected inventory, safety, reorder, DOS, risk |
| FactOptimizationRecommendation | Product-supplier-warehouse-date | integer order, costs, impact, status, diagnostics |
| FactOptimizationAllocation | Recommendation-warehouse | allocation, capacity before/after, cost |
| FactScenarioResult | Scenario-product-warehouse-date | preserved baseline and scenario demand/revenue/inventory/cost/profit |
| FactDataQuality | One quality check/run | severity, status, checked/failed counts, details |

The authoritative column types, constraints, foreign keys, and defaults are in
`database/schema/*.sql` and `database/migrations/*.sql`.
