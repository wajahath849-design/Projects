# Seven-page report specification and visual mappings

Use a 16:9 canvas, 24 px outer margins, a 56 px title band, and a 12-column grid.
Apply `decision_intelligence_theme.json` before constructing visuals.

## Page 1 — Executive Overview

- Top row: KPI cards for Total Revenue, Forecast Revenue, Total Forecast Demand,
  Inventory Value, Products at Stockout Risk, Critical Products, Recommended Purchase
  Cost, Expected Revenue Protected, Forecast Accuracy, and Optimization Savings.
- Middle left (8 columns): line chart, axis `Date[FullDate]`, values Total Actual Demand and
  Total Forecast Demand.
- Middle right (4 columns): stacked bar, axis `Inventory Intelligence[CategoryID]`, legend
  RiskClassification, value distinct ProductID.
- Bottom left: recommendation table with ProductID, SupplierID, WarehouseID, Recommended
  Order Quantity, RecommendationPriority, and Expected Revenue Protected.
- Bottom center: filled map or bar chart using StateID and Forecast Revenue.
- Bottom right: card using `AI Insight Text`; slicer using ScenarioName.

## Page 2 — Demand Forecast

- Main line chart: FullDate, ActualDemand and ForecastDemand; add LowerBound and UpperBound
  as uncertainty series or an error-band custom visual approved by the organization.
- Clustered bars: ForecastDemand by ProductID and CategoryID.
- Slicers: HorizonDays, ProductID, CategoryID, StoreID, StateID, and ModelName.
- KPI cards: Forecast Growth Percentage, Forecast Bias, WAPE, and Forecast Accuracy.
- Driver tables: FeatureName, ShapValue, Direction, and ContributionRank from the explanation
  view or API export; filter one table to POSITIVE and one to NEGATIVE.

## Page 3 — Inventory Intelligence

- Cards: Current Inventory, Average Days of Supply, Products Below Reorder Point, Products
  at Stockout Risk, Excess Inventory Units, and Warehouse Utilization.
- Donut: distinct ProductID by RiskClassification.
- Table: ProductID, WarehouseID, CurrentInventory, SafetyStock, ReorderPoint,
  ProjectedInventory, DaysOfSupply, StockoutProbability, and RiskClassification.
- Warehouse utilization bar: WarehouseID and CurrentUtilization with a 90% conditional line.
- Projected inventory timeline: FullDate, ProductID, and ProjectedInventory.

## Page 4 — Optimization Recommendations

- Cards: Recommended Order Quantity, Recommended Purchase Cost, Expected Cost Savings,
  Expected Revenue Protected, and Expected Stockout Reduction.
- Sankey or matrix: SupplierID > WarehouseID > ProductID using AllocatedQuantity.
- Constraint utilization bars: CapacityBefore versus CapacityAfter by WarehouseID.
- Detail table: RecommendationID, ProductID, SupplierID, WarehouseID, quantity, dates,
  ExpectedTotalCost, SolverStatus, RecommendationPriority, and DiagnosticMessage.
- Slicers: SolverStatus, priority, supplier, warehouse, and product.

## Page 5 — Scenario Simulation

- ScenarioName single-select slicer plus baseline/scenario KPI cards.
- Cards: Scenario Demand Impact, Scenario Revenue Impact, Scenario Cost Impact,
  Scenario Profit Impact, Scenario Stockout Impact, and order-quantity difference.
- Waterfall: Demand, revenue, purchase cost, transportation cost, holding cost, and profit
  changes from baseline.
- Sensitivity chart: ScenarioValue on axis, ScenarioProfit on value, ScenarioType as legend.
- Before/after clustered columns for demand, inventory, order quantity, cost, and profit.

## Page 6 — Model Performance

- Comparison matrix: ModelName, WAPE, RMSE, MAE, Bias, SMAPE, TrainingTimeSeconds, and
  InferenceTimeSeconds.
- Highlight IsProduction with blue background and a winning-model card.
- Clustered bars for WAPE/RMSE/MAE by ModelName; diverging bar for Bias.
- Category performance table using CategoryID; residual distribution from exported holdout
  predictions can be loaded as an optional supplemental table.

## Page 7 — Data Quality and Pipeline Health

- Cards: total checks, passed checks, warnings, Failed Quality Checks, Records Processed,
  Last Pipeline Run, and Data Quality Pass Rate.
- Stacked bar: count of CheckName by TableName and Status.
- Trend: FullDate and Data Quality Pass Rate.
- Detail table: CheckName, CheckCategory, Severity, Status, RecordsChecked, FailedRecords,
  FailurePercentage, CreatedAt, and DataVersion.

## Drill-through and tooltip specifications

- Configure Page 3 as product drill-through using ProductID; keep all filters enabled.
- Configure Page 4 as supplier/warehouse drill-through using SupplierID and WarehouseID.
- Add a back button to drill-through targets.
- Forecast tooltips: actual, forecast, variance, bounds, confidence, horizon, and model.
- Inventory tooltips: current, projected, safety stock, reorder point, days supply, probability.
- Recommendation tooltips: all cost components, protected revenue, priority, and status.
- Scenario tooltips: baseline value, scenario value, demand/cost/profit/stockout impacts.
