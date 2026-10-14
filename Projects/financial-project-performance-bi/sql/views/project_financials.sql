CREATE VIEW IF NOT EXISTS v_project_financials AS
WITH selected_budget AS (
  SELECT b.project_id, SUM(b.allocated_budget_usd) AS approved_budget_usd
  FROM FactBudget b JOIN DimBudgetVersion v ON b.version_id = v.version_id
  WHERE v.is_selected_approved = 1 GROUP BY b.project_id
), costs AS (
  SELECT project_id, SUM(amount) AS actual_cost_usd FROM FactActualCost GROUP BY project_id
), revenues AS (
  SELECT project_id, SUM(recognized_revenue_usd) AS recognized_revenue_usd FROM FactRevenue GROUP BY project_id
), etc AS (
  SELECT project_id, SUM(forecast_cost_usd) AS estimate_to_complete_usd
  FROM FactForecast WHERE is_latest_valid = 1 AND scenario = 'base' GROUP BY project_id
)
SELECT p.project_id, p.project_name, b.approved_budget_usd,
       COALESCE(c.actual_cost_usd, 0) AS actual_cost_usd,
       COALESCE(r.recognized_revenue_usd, 0) AS recognized_revenue_usd,
       b.approved_budget_usd - COALESCE(c.actual_cost_usd, 0) AS budget_variance_usd,
       COALESCE(r.recognized_revenue_usd, 0) - COALESCE(c.actual_cost_usd, 0) AS gross_profit_usd,
       COALESCE(e.estimate_to_complete_usd, 0) AS estimate_to_complete_usd,
       COALESCE(c.actual_cost_usd, 0) + COALESCE(e.estimate_to_complete_usd, 0) AS estimate_at_completion_usd
FROM DimProject p JOIN selected_budget b USING(project_id)
LEFT JOIN costs c USING(project_id) LEFT JOIN revenues r USING(project_id) LEFT JOIN etc e USING(project_id);
