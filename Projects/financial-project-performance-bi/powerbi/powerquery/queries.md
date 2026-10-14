# Power Query setup

Create a text parameter named `CuratedFolder` pointing to the absolute `data\curated` folder. Create a blank query named `fnLoadCsv` by pasting `fnLoadCsv.pq`. Create the queries below in the Advanced Editor, each with the specified name. Do not load `ProjectMetrics` as a fact alongside the modeled facts; it is a reconciliation output and would double count.

```powerquery
// DimProject
let Source = fnLoadCsv("DimProject.csv", {{"project_id", type text}, {"project_name", type text}, {"client_id", type text}, {"manager_id", type text}, {"primary_department_id", type text}, {"start_date", type date}, {"planned_end_date", type date}, {"status", type text}, {"completion_pct", type number}, {"scenario_tag", type text}, {"contract_value_usd", Currency.Type}}) in Source

// DimDate
let Source = fnLoadCsv("DimDate.csv", {{"date", type date}, {"date_key", Int64.Type}, {"year", Int64.Type}, {"month_number", Int64.Type}, {"year_month", type text}, {"month_start", type date}}) in Source

// DimDepartment
let Source = fnLoadCsv("DimDepartment.csv", {{"department_id", type text}, {"department_name", type text}}) in Source

// DimCostCategory
let Source = fnLoadCsv("DimCostCategory.csv", {{"category_id", type text}, {"category_name", type text}, {"cost_group", type text}}) in Source

// DimClient
let Source = fnLoadCsv("DimClient.csv", {{"client_id", type text}, {"client_name", type text}}) in Source

// DimProjectManager
let Source = fnLoadCsv("DimProjectManager.csv", {{"manager_id", type text}, {"manager_name", type text}}) in Source

// DimBudgetVersion
let Source = fnLoadCsv("DimBudgetVersion.csv", {{"version_id", type text}, {"project_id", type text}, {"version_number", Int64.Type}, {"approval_status", type text}, {"approved_date", type date}, {"is_selected_approved", type logical}}) in Source

// FactBudget
let Source = fnLoadCsv("FactBudget.csv", {{"budget_record_id", type text}, {"project_id", type text}, {"version_id", type text}, {"version_number", Int64.Type}, {"approval_status", type text}, {"approved_date", type date}, {"department_id", type text}, {"allocated_budget_usd", Currency.Type}, {"date_key", Int64.Type}}) in Source

// FactActualCost
let Source = fnLoadCsv("FactActualCost.csv", {{"transaction_id", type text}, {"project_id", type text}, {"department_id", type text}, {"category_id", type text}, {"transaction_date", type date}, {"amount", Currency.Type}, {"currency", type text}, {"description", type text}, {"date_key", Int64.Type}}) in Source

// FactRevenue
let Source = fnLoadCsv("FactRevenue.csv", {{"revenue_id", type text}, {"project_id", type text}, {"recognition_date", type date}, {"recognized_revenue_usd", Currency.Type}, {"currency", type text}, {"date_key", Int64.Type}}) in Source

// FactForecast
let Source = fnLoadCsv("FactForecast.csv", {{"forecast_id", type text}, {"project_id", type text}, {"snapshot_date", type date}, {"forecast_month", type date}, {"date_key", Int64.Type}, {"scenario", type text}, {"forecast_cost_usd", Currency.Type}, {"is_latest_valid", type logical}, {"baseline_monthly_usd", Currency.Type}, {"actual_at_snapshot_usd", Currency.Type}, {"approved_budget_usd", Currency.Type}}) in Source

// DataQualityExceptions
let Source = Csv.Document(File.Contents(ReportFolder & "\data_quality_exceptions.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]), Typed = Table.TransformColumnTypes(Headers, {{"source", type text}, {"source_row", Int64.Type}, {"record_id", type text}, {"reason", type text}}) in Typed

// SourceManifest
let Source = Csv.Document(File.Contents(ReportFolder & "\source_manifest.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]), Typed = Table.TransformColumnTypes(Headers, {{"source", type text}, {"path", type text}, {"sha256", type text}, {"rows", Int64.Type}, {"bytes", Int64.Type}, {"modified_utc", type text}}) in Typed

// ForecastHoldout
let Source = Csv.Document(File.Contents(ReportFolder & "\forecast_holdout.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]), Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]), Typed = Table.TransformColumnTypes(Headers, {{"project_id", type text}, {"snapshot_date", type date}, {"holdout_months", Int64.Type}, {"actual_usd", Currency.Type}, {"baseline_forecast_usd", Currency.Type}, {"absolute_error_usd", Currency.Type}}) in Typed

// RefreshAudit
let Source = Json.Document(File.Contents(ReportFolder & "\refresh_report.json")), Row = #table({"status", "refreshed_at_utc", "as_of_date", "rejected_rows", "budget_delta_usd", "actual_delta_usd", "revenue_delta_usd", "orphan_count", "forecast_holdout_mae_usd"}, {{Source[status], DateTimeZone.FromText(Source[refreshed_at_utc]), Date.FromText(Source[as_of_date]), Source[rejected_rows], Source[reconciliation][budget_delta_usd], Source[reconciliation][actual_delta_usd], Source[reconciliation][revenue_delta_usd], Source[reconciliation][orphan_count], Source[forecast_holdout_mae_usd]}}) in Row
```

Name the second text parameter `ReportFolder`. The audit tables are intentionally disconnected from the financial model. Use `RefreshAudit` fields directly for single-row status cards and `ForecastHoldout[absolute_error_usd]` for project-level error detail.
