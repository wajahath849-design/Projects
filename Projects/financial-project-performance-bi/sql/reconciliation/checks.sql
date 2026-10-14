SELECT 'budget', ROUND(SUM(approved_budget_usd), 2) FROM v_project_financials
UNION ALL SELECT 'actual_cost', ROUND(SUM(actual_cost_usd), 2) FROM v_project_financials
UNION ALL SELECT 'recognized_revenue', ROUND(SUM(recognized_revenue_usd), 2) FROM v_project_financials;
