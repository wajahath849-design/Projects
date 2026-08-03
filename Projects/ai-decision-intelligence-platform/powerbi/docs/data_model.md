# Power BI data model and Power Query

No `.pbix` file is included. Build the report in Power BI Desktop using the package below.

## Connection and Power Query

1. Open **Get data > SQL Server**.
2. Server: `localhost\SQLEXPRESS`; database: `AIDecisionIntelligence`.
3. Use Windows authentication. Choose Import for the portfolio sample or DirectQuery for
   a larger operational demonstration.
4. Import these views and rename them as shown:

| SQL object | Power BI table |
|---|---|
| `vw_PBI_ExecutiveOverview` | Executive Overview |
| `vw_PBI_DemandForecast` | Demand Forecast |
| `vw_PBI_InventoryIntelligence` | Inventory Intelligence |
| `vw_PBI_OptimizationRecommendations` | Optimization Recommendations |
| `vw_PBI_ScenarioComparison` | Scenario Comparison |
| `vw_PBI_ModelPerformance` | Model Performance |
| `vw_PBI_DataQuality` | Data Quality |
| `vw_PBI_ForecastExplanations` | Forecast Explanations |
| `DimDate` | Date |
| `DimProduct` | Product |
| `DimWarehouse` | Warehouse |
| `DimSupplier` | Supplier |
| `DimScenario` | Scenario |

Reusable Power Query pattern:

```powerquery
let
    ServerName = "localhost\SQLEXPRESS",
    DatabaseName = "AIDecisionIntelligence",
    Source = Sql.Database(ServerName, DatabaseName),
    View = Source{[Schema="dbo", Item="vw_PBI_DemandForecast"]}[Data],
    Typed = Table.TransformColumnTypes(View, {
        {"DateKey", Int64.Type}, {"FullDate", type date},
        {"ActualDemand", type number}, {"ForecastDemand", type number}
    })
in
    Typed
```

Create `ServerName` and `DatabaseName` as Power Query parameters before publishing.
Do not place credentials in M code. Disable automatic date/time and mark `Date[FullDate]`
as the model date table.

## Relationships

Use single-direction, one-to-many relationships from dimensions to facts:

| One side | Many side | Key |
|---|---|---|
| Date | Executive Overview | DateKey |
| Date | Demand Forecast | DateKey |
| Date | Inventory Intelligence | DateKey |
| Date | Optimization Recommendations | DateKey |
| Date | Scenario Comparison | DateKey |
| Product | Demand Forecast | ProductKey |
| Product | Inventory Intelligence | ProductKey |
| Product | Optimization Recommendations | ProductKey |
| Warehouse | Inventory Intelligence | WarehouseKey |
| Warehouse | Optimization Recommendations | WarehouseKey |

`Model Performance`, `Data Quality`, and `Scenario Comparison` can remain intentionally
disconnected from some dimensions where the SQL view already supplies the reporting grain.
Use `Scenario[ScenarioID]` to `Scenario Comparison[ScenarioID]` only if both columns are
configured with identical text types. Avoid bidirectional filters and many-to-many joins.

## Model settings

- Hide surrogate keys, run IDs, pipeline IDs, and diagnostic fields from report view.
- Format currency as `$#,0.00`; quantities as `#,0.0`; probabilities and rates as `0.0%`.
- Sort month names by `Date[MonthNumber]` and risk labels using a small manual sort table:
  Critical 1, At Risk 2, Healthy 3, Excess 4, Obsolete Risk 5.
- Put all measures from `dax/measures.dax` in a dedicated `_Measures` table.
- Configure incremental refresh on `FullDate` for full-data mode; sample mode can refresh all.
