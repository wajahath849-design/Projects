-- Optional SQLite analytical staging. The Python loader writes all curated tables.
PRAGMA foreign_keys = ON;
CREATE INDEX IF NOT EXISTS ix_cost_project_date ON FactActualCost(project_id, date_key);
CREATE INDEX IF NOT EXISTS ix_revenue_project_date ON FactRevenue(project_id, date_key);
CREATE INDEX IF NOT EXISTS ix_budget_project_version ON FactBudget(project_id, version_id);
CREATE INDEX IF NOT EXISTS ix_forecast_project_snapshot ON FactForecast(project_id, snapshot_date, scenario);
