from pathlib import Path


def test_bi_views_have_single_current_definitions() -> None:
    sql = Path("sql/01_views.sql").read_text()
    assert sql.count("CREATE OR REPLACE VIEW vw_forecast_accuracy AS") == 1
    assert sql.count("CREATE OR REPLACE VIEW vw_supplier_performance AS") == 1
    assert "vw_latest_successful_model_run" in sql
    assert "vw_transfer_recommendations_current" in sql
    assert "vw_fact_inventory_daily" in sql


def test_schema_supports_multi_line_po_accuracy_and_job_recovery() -> None:
    sql = Path("sql/00_schema.sql").read_text()
    assert "UNIQUE (supplier_id, purchase_order_no, warehouse_id, sku_id)" in sql
    assert "absolute_error_sum" in sql
    assert "attempts INTEGER" in sql
    assert "decision_at TIMESTAMPTZ" in sql
