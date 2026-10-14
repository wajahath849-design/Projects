# Data dictionary

All amounts are USD. The source records and outputs are **synthetic demonstration data**.

| Table | Primary/business key | Important fields and meaning |
|---|---|---|
| DimProject | `project_id` | Project name, client and manager IDs, primary department, start/end dates, status, delivery `completion_pct`, `scenario_tag`, synthetic contract value. Completion is supplied delivery progress, not inferred from spend. |
| DimDate | `date_key` | Calendar date, year, month number, year-month, month start. |
| DimDepartment | `department_id` | Six cost-owning departments. |
| DimCostCategory | `category_id` | Six categories and labor/nonlabor `cost_group`. |
| DimClient | `client_id` | Fictional client labels. |
| DimProjectManager | `manager_id` | Fictional manager labels. |
| DimBudgetVersion | `version_id` | Project, version sequence, approval status/date, selected approved flag. |
| FactBudget | `budget_record_id` | Project, version, department, `allocated_budget_usd`, approval `date_key`. Full version allocations sum to its lifetime total. |
| FactActualCost | `transaction_id` | Project, department, category, transaction date/key, signed `amount`, currency, description. Negative values are valid corrections. |
| FactRevenue | `revenue_id` | Project, recognition date/key, `recognized_revenue_usd`; no cash or invoice claim. |
| FactForecast | `forecast_id` | Project, snapshot date, future month/key, scenario, monthly `forecast_cost_usd`, selected-snapshot flag, monthly baseline and actual/budget at snapshot. |
| ProjectMetrics | `project_id` | Reconciled project-level diagnostic extract. Do not relate this to modeled facts in Power BI. |
| data_quality_exceptions | source + source row | Quarantined record ID and first applicable reason. |
| source_manifest | source | Relative path, SHA-256, source row count, file size. |

Missing project keys and invalid category/department references are rejected. Currency is expected to be USD and is case-insensitively validated. Date parsing is strict enough to quarantine invalid dates or dates before project start. Financial amounts are parsed as numeric without removing valid negative corrections. The four deliberate cost-source exceptions are a duplicate ID, blank project key, unknown category, and pre-start date.

