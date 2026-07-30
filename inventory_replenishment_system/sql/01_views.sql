SET search_path TO inventory, public;

CREATE OR REPLACE VIEW vw_latest_successful_model_run AS
SELECT model_run_id, model_name, model_version, finished_at
FROM model_runs
WHERE status = 'SUCCEEDED'
ORDER BY finished_at DESC NULLS LAST, model_run_id DESC
LIMIT 1;

CREATE OR REPLACE VIEW vw_latest_inventory AS
SELECT DISTINCT ON (s.warehouse_id, s.sku_id)
    s.warehouse_id,
    s.sku_id,
    s.snapshot_ts,
    s.on_hand_qty,
    s.allocated_qty,
    s.on_order_qty,
    s.backorder_qty,
    (s.on_hand_qty + s.on_order_qty - s.allocated_qty - s.backorder_qty) AS inventory_position_qty
FROM inventory_snapshots s
ORDER BY s.warehouse_id, s.sku_id, s.snapshot_ts DESC;

CREATE OR REPLACE VIEW vw_fact_forecast AS
SELECT
    f.model_run_id,
    f.forecast_date,
    f.warehouse_id,
    f.sku_id,
    f.forecast_qty,
    f.lower_qty,
    f.upper_qty,
    f.model_name,
    f.created_at
FROM demand_forecasts f;

CREATE OR REPLACE VIEW vw_fact_forecast_current AS
SELECT f.*
FROM vw_fact_forecast f
JOIN vw_latest_successful_model_run lr ON lr.model_run_id = f.model_run_id;

CREATE OR REPLACE VIEW vw_fact_replenishment AS
SELECT
    r.model_run_id,
    r.recommendation_id,
    r.recommendation_date,
    r.warehouse_id,
    r.sku_id,
    r.supplier_id,
    r.service_level,
    r.avg_daily_demand,
    r.demand_stddev,
    r.avg_lead_time_days,
    r.lead_time_stddev,
    r.safety_stock_qty,
    r.reorder_point_qty,
    r.target_stock_qty,
    r.inventory_position_qty,
    r.gross_recommended_order_qty,
    r.recommended_order_qty,
    r.expected_stockout_date,
    r.risk_band,
    r.calculation_details,
    r.created_at
FROM replenishment_recommendations r;

CREATE OR REPLACE VIEW vw_fact_replenishment_current AS
SELECT r.*
FROM vw_fact_replenishment r
JOIN vw_latest_successful_model_run lr ON lr.model_run_id = r.model_run_id;

CREATE OR REPLACE VIEW vw_latest_replenishment AS
SELECT * FROM vw_fact_replenishment_current;

CREATE OR REPLACE VIEW vw_fact_inventory_current AS
SELECT
    warehouse_id,
    sku_id,
    snapshot_ts,
    on_hand_qty,
    allocated_qty,
    on_order_qty,
    backorder_qty,
    inventory_position_qty
FROM vw_latest_inventory;

CREATE OR REPLACE VIEW vw_fact_inventory_daily AS
SELECT DISTINCT ON (s.snapshot_ts::DATE, s.warehouse_id, s.sku_id)
    s.snapshot_ts::DATE AS snapshot_date,
    s.warehouse_id,
    s.sku_id,
    s.on_hand_qty,
    s.allocated_qty,
    s.on_order_qty,
    s.backorder_qty,
    (s.on_hand_qty + s.on_order_qty - s.allocated_qty - s.backorder_qty) AS inventory_position_qty
FROM inventory_snapshots s
ORDER BY s.snapshot_ts::DATE, s.warehouse_id, s.sku_id, s.snapshot_ts DESC;

CREATE OR REPLACE VIEW vw_fact_daily_demand AS
SELECT
    transaction_ts::DATE AS demand_date,
    warehouse_id,
    sku_id,
    SUM(ABS(quantity)) AS demand_qty,
    SUM(ABS(quantity) * COALESCE(unit_cost, 0)) AS demand_value
FROM inventory_transactions
WHERE transaction_type IN ('SALE','TRANSFER_OUT','DAMAGE')
GROUP BY transaction_ts::DATE, warehouse_id, sku_id;

CREATE OR REPLACE VIEW vw_inventory_control_tower AS
SELECT
    li.warehouse_id,
    w.warehouse_code,
    w.warehouse_name,
    w.region,
    li.sku_id,
    s.sku_code,
    s.sku_name,
    s.category,
    s.unit_cost,
    li.snapshot_ts,
    li.on_hand_qty,
    li.allocated_qty,
    li.on_order_qty,
    li.backorder_qty,
    li.inventory_position_qty,
    rr.model_run_id,
    rr.supplier_id,
    rr.service_level,
    rr.safety_stock_qty,
    rr.reorder_point_qty,
    rr.gross_recommended_order_qty,
    rr.recommended_order_qty,
    rr.expected_stockout_date,
    rr.risk_band,
    CASE
        WHEN rr.avg_daily_demand > 0 THEN li.inventory_position_qty / rr.avg_daily_demand
        ELSE NULL
    END AS simple_days_of_supply,
    li.on_hand_qty * s.unit_cost AS inventory_value,
    sup.supplier_code,
    sup.supplier_name
FROM vw_latest_inventory li
JOIN dim_warehouse w ON w.warehouse_id = li.warehouse_id
JOIN dim_sku s ON s.sku_id = li.sku_id
LEFT JOIN vw_fact_replenishment_current rr
    ON rr.warehouse_id = li.warehouse_id AND rr.sku_id = li.sku_id
LEFT JOIN dim_supplier sup ON sup.supplier_id = rr.supplier_id;

CREATE OR REPLACE VIEW vw_supplier_performance AS
SELECT
    sup.supplier_id,
    sup.supplier_code,
    sup.supplier_name,
    w.warehouse_id,
    w.warehouse_code,
    COUNT(*) FILTER (WHERE e.receipt_date IS NOT NULL) AS completed_order_lines,
    COUNT(*) FILTER (WHERE e.receipt_date IS NOT NULL AND e.promised_date IS NOT NULL) AS on_time_eligible_order_lines,
    AVG(e.actual_lead_time_days) FILTER (WHERE e.receipt_date IS NOT NULL) AS avg_actual_lead_time_days,
    STDDEV_SAMP(e.actual_lead_time_days) FILTER (WHERE e.receipt_date IS NOT NULL) AS lead_time_stddev_days,
    sup.contractual_lead_time_days,
    AVG(e.actual_lead_time_days - sup.contractual_lead_time_days)
        FILTER (WHERE e.receipt_date IS NOT NULL) AS avg_sla_variance_days,
    AVG(CASE WHEN e.receipt_date <= e.promised_date THEN 1.0 ELSE 0.0 END)
        FILTER (WHERE e.receipt_date IS NOT NULL AND e.promised_date IS NOT NULL) AS on_time_delivery_rate
FROM supplier_lead_time_events e
JOIN dim_supplier sup ON sup.supplier_id = e.supplier_id
JOIN dim_warehouse w ON w.warehouse_id = e.warehouse_id
GROUP BY sup.supplier_id, sup.supplier_code, sup.supplier_name,
         w.warehouse_id, w.warehouse_code, sup.contractual_lead_time_days;

CREATE OR REPLACE VIEW vw_forecast_accuracy AS
SELECT
    a.model_run_id,
    a.metric_date,
    a.warehouse_id,
    w.warehouse_code,
    a.sku_id,
    s.sku_code,
    s.category,
    a.mae,
    a.rmse,
    a.wape,
    a.bias,
    a.sample_count,
    a.absolute_error_sum,
    a.actual_sum,
    a.forecast_sum,
    mr.model_name,
    mr.model_version
FROM forecast_accuracy a
JOIN dim_warehouse w ON w.warehouse_id = a.warehouse_id
JOIN dim_sku s ON s.sku_id = a.sku_id
JOIN model_runs mr ON mr.model_run_id = a.model_run_id;

CREATE OR REPLACE VIEW vw_transfer_recommendations AS
SELECT
    tr.model_run_id,
    tr.sku_id,
    sku.sku_code,
    tr.from_warehouse_id,
    wf.warehouse_code AS from_warehouse_code,
    tr.to_warehouse_id,
    wt.warehouse_code AS to_warehouse_code,
    tr.transfer_qty,
    tr.status,
    tr.created_at
FROM inventory_transfer_recommendations tr
JOIN dim_sku sku ON sku.sku_id = tr.sku_id
JOIN dim_warehouse wf ON wf.warehouse_id = tr.from_warehouse_id
JOIN dim_warehouse wt ON wt.warehouse_id = tr.to_warehouse_id;

CREATE OR REPLACE VIEW vw_transfer_recommendations_current AS
SELECT tr.*
FROM vw_transfer_recommendations tr
JOIN vw_latest_successful_model_run lr ON lr.model_run_id = tr.model_run_id;
