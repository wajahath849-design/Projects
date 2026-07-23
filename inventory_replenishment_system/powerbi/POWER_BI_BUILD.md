# Power BI semantic model and dashboard build

## Recommended storage design

Use a composite model:

- Import: `dim_date`, `dim_warehouse`, `dim_sku`, `dim_supplier`, `vw_fact_daily_demand`, `vw_fact_inventory_daily`, `vw_fact_forecast_current`, `vw_fact_replenishment_current`, `vw_fact_forecast`, `vw_fact_replenishment`, `vw_forecast_accuracy`, `vw_supplier_performance`, and `vw_transfer_recommendations_current`.
- DirectQuery: `vw_fact_inventory_current` and optionally `vw_inventory_control_tower` for operational wallboard tiles.

For a simpler portfolio version, use Import for every table and schedule refresh. Configure incremental refresh on daily demand and forecast facts.

## Rename tables in Power BI

- `inventory.dim_date` -> `Dim Date`
- `inventory.dim_warehouse` -> `Dim Warehouse`
- `inventory.dim_sku` -> `Dim SKU`
- `inventory.dim_supplier` -> `Dim Supplier`
- `inventory.vw_fact_daily_demand` -> `Fact Daily Demand`
- `inventory.vw_fact_forecast_current` -> `Fact Forecast Current`
- `inventory.vw_fact_replenishment_current` -> `Fact Replenishment Current`
- `inventory.vw_fact_forecast` -> `Fact Forecast History`
- `inventory.vw_fact_replenishment` -> `Fact Replenishment History`
- `inventory.vw_fact_inventory_current` -> `Fact Inventory Current`
- `inventory.vw_fact_inventory_daily` -> `Fact Inventory Daily`
- `inventory.vw_forecast_accuracy` -> `Forecast Accuracy`
- `inventory.vw_supplier_performance` -> `Supplier Performance`
- `inventory.vw_transfer_recommendations_current` -> `Transfer Recommendations Current`
- `inventory.vw_transfer_recommendations` -> `Transfer Recommendations History`
- `inventory.operational_overrides` -> `Operational Overrides`

## Relationships

Create single-direction, one-to-many relationships from dimensions to facts:

- `Dim Date[date_value]` -> `Fact Daily Demand[demand_date]`
- `Dim Date[date_value]` -> `Fact Inventory Daily[snapshot_date]`
- `Dim Date[date_value]` -> `Fact Forecast Current[forecast_date]` and `Fact Forecast History[forecast_date]`
- `Dim Date[date_value]` -> `Fact Replenishment Current[recommendation_date]` and `Fact Replenishment History[recommendation_date]`
- `Dim Warehouse[warehouse_id]` -> each fact's `warehouse_id`
- `Dim SKU[sku_id]` -> each fact's `sku_id`
- `Dim Supplier[supplier_id]` -> current and historical replenishment facts' `supplier_id`, and `Supplier Performance[supplier_id]`
- `Dim Warehouse[warehouse_id]` -> `Supplier Performance[warehouse_id]`
- For transfers, create two role-playing copies: `Dim Warehouse From` -> `Transfer Recommendations Current[from_warehouse_id]` and `Dim Warehouse To` -> `Transfer Recommendations Current[to_warehouse_id]`. Do not activate two competing relationships from one warehouse dimension.

Avoid bidirectional filtering unless a specific many-to-many requirement has been proven.

## Dashboard pages

### 1. Executive Control Tower

- KPI cards: Inventory Value, Critical SKU Count, High Risk SKU Count, Recommended Order Quantity, On-Time Delivery Rate, and Inventory Turns.
- Region/warehouse risk heatmap.
- Inventory value by category.
- Stockout risk trend.
- Top 10 emergency reorder SKUs.

### 2. Replenishment Operations

- Matrix: Warehouse > Category > SKU.
- Columns: On Hand, Inventory Position, Safety Stock, Reorder Point, Days of Supply Remaining, Recommended Order Quantity, Reorder Status.
- Conditional formatting by risk band.
- Demand spike parameter slicer from 0.5x to 2.0x.
- Drill-through to SKU detail.

### 3. Supplier Performance

- On-time delivery rate by supplier.
- Actual lead time vs contractual SLA scatter plot.
- Lead-time variance trend.
- Delayed purchase-order detail table.

### 4. Forecast Quality

- Actual vs forecast line chart.
- WAPE, MAE and bias cards.
- Accuracy by SKU/category.
- Model fallback count: LightGBM vs seasonal naive.

### 5. Overrides and Governance

- Pending/approved/rejected override counts.
- Override audit table with submitter, approver, reason and validity window.
- Replenishment changes caused by active overrides.

## Visual interaction rules

- Global slicers: Region, Warehouse, Category, Supplier, Date.
- Keep Date/Region/Warehouse relationships on dimensions, not fact-to-fact.
- Disable unnecessary visual interactions on large detail tables.
- Use tooltips for uncertainty range, lead-time variance and override reason.

## Measure formatting and correctness

- Format `Forecast WAPE`, `Forecast Bias`, `Latest Forecast WAPE`, `Latest Forecast Bias`, and `On-Time Delivery Rate` as percentages.
- The supplied WAPE measure aggregates absolute error and actual demand totals; it does not average SKU-level percentages.
- Supplier on-time performance is weighted by eligible completed order lines.
- Inventory Turns uses the daily inventory snapshot history rather than current inventory as a proxy.
- Operational order and transfer cards use only the latest successful model-run views, preventing partial failed runs or historical runs from being double-counted.
