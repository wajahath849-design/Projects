CREATE SCHEMA IF NOT EXISTS inventory;
SET search_path TO inventory, public;

CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_code VARCHAR(40) NOT NULL UNIQUE,
    supplier_name VARCHAR(200) NOT NULL,
    contact_email VARCHAR(320),
    contractual_lead_time_days NUMERIC(10,2) NOT NULL DEFAULT 7 CHECK (contractual_lead_time_days >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_warehouse (
    warehouse_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_code VARCHAR(40) NOT NULL UNIQUE,
    warehouse_name VARCHAR(200) NOT NULL,
    region VARCHAR(100) NOT NULL,
    timezone VARCHAR(80) NOT NULL DEFAULT 'UTC',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_sku (
    sku_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku_code VARCHAR(80) NOT NULL UNIQUE,
    sku_name VARCHAR(240) NOT NULL,
    category VARCHAR(120) NOT NULL,
    unit_cost NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    minimum_order_qty NUMERIC(18,4) NOT NULL DEFAULT 1 CHECK (minimum_order_qty > 0),
    order_multiple NUMERIC(18,4) NOT NULL DEFAULT 1 CHECK (order_multiple > 0),
    shelf_life_days INTEGER CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_sku (
    supplier_id BIGINT NOT NULL REFERENCES dim_supplier(supplier_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    priority_rank INTEGER NOT NULL DEFAULT 1 CHECK (priority_rank > 0),
    supplier_sku_code VARCHAR(100),
    unit_purchase_cost NUMERIC(18,4) CHECK (unit_purchase_cost IS NULL OR unit_purchase_cost >= 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (supplier_id, sku_id)
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_transaction_id VARCHAR(120) NOT NULL,
    transaction_ts TIMESTAMPTZ NOT NULL,
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    transaction_type VARCHAR(30) NOT NULL CHECK (transaction_type IN ('SALE','RECEIPT','ADJUSTMENT','TRANSFER_IN','TRANSFER_OUT','RETURN','DAMAGE')),
    quantity NUMERIC(18,4) NOT NULL,
    unit_cost NUMERIC(18,4) CHECK (unit_cost IS NULL OR unit_cost >= 0),
    source_system VARCHAR(80) NOT NULL DEFAULT 'CSV',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_system, source_transaction_id)
);

CREATE TABLE IF NOT EXISTS inventory_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_ts TIMESTAMPTZ NOT NULL,
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    on_hand_qty NUMERIC(18,4) NOT NULL CHECK (on_hand_qty >= 0),
    allocated_qty NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (allocated_qty >= 0),
    on_order_qty NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (on_order_qty >= 0),
    backorder_qty NUMERIC(18,4) NOT NULL DEFAULT 0 CHECK (backorder_qty >= 0),
    source_system VARCHAR(80) NOT NULL DEFAULT 'WMS',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (snapshot_ts, warehouse_id, sku_id)
);

CREATE TABLE IF NOT EXISTS supplier_lead_time_events (
    lead_time_event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_id BIGINT NOT NULL REFERENCES dim_supplier(supplier_id),
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    purchase_order_no VARCHAR(100) NOT NULL,
    promised_date DATE,
    order_date DATE NOT NULL,
    receipt_date DATE,
    actual_lead_time_days NUMERIC(10,2) GENERATED ALWAYS AS (
        CASE WHEN receipt_date IS NULL THEN NULL ELSE (receipt_date - order_date)::NUMERIC END
    ) STORED,
    delay_reason VARCHAR(240),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (supplier_id, purchase_order_no, warehouse_id, sku_id)
);

CREATE TABLE IF NOT EXISTS external_signals (
    signal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signal_date DATE NOT NULL,
    region VARCHAR(100) NOT NULL,
    signal_type VARCHAR(80) NOT NULL,
    signal_value NUMERIC(18,6) NOT NULL,
    source_name VARCHAR(120) NOT NULL,
    source_reference TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (signal_date, region, signal_type, source_name)
);

CREATE TABLE IF NOT EXISTS operational_overrides (
    override_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    override_type VARCHAR(40) NOT NULL CHECK (override_type IN ('PHYSICAL_COUNT','DEMAND_MULTIPLIER','LEAD_TIME_PENALTY','SAFETY_STOCK','REORDER_QTY','HOLD_REPLENISHMENT')),
    numeric_value NUMERIC(18,6),
    text_value VARCHAR(500),
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    reason VARCHAR(500) NOT NULL,
    submitted_by VARCHAR(160) NOT NULL,
    approved_by VARCHAR(160),
    decision_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
    source VARCHAR(40) NOT NULL DEFAULT 'EXCEL',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (effective_to IS NULL OR effective_to > effective_from),
    CHECK (numeric_value IS NOT NULL OR text_value IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name VARCHAR(80) NOT NULL,
    model_version VARCHAR(80) NOT NULL,
    training_start_date DATE,
    training_end_date DATE,
    horizon_days INTEGER NOT NULL CHECK (horizon_days > 0),
    parameters JSONB NOT NULL DEFAULT '{}'::JSONB,
    status VARCHAR(20) NOT NULL CHECK (status IN ('RUNNING','SUCCEEDED','FAILED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS demand_forecasts (
    forecast_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id BIGINT NOT NULL REFERENCES model_runs(model_run_id),
    forecast_date DATE NOT NULL,
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    forecast_qty NUMERIC(18,6) NOT NULL CHECK (forecast_qty >= 0),
    lower_qty NUMERIC(18,6) NOT NULL CHECK (lower_qty >= 0),
    upper_qty NUMERIC(18,6) NOT NULL CHECK (upper_qty >= lower_qty),
    model_name VARCHAR(80) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (model_run_id, forecast_date, warehouse_id, sku_id)
);

CREATE TABLE IF NOT EXISTS forecast_accuracy (
    accuracy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id BIGINT NOT NULL REFERENCES model_runs(model_run_id),
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    metric_date DATE NOT NULL,
    mae NUMERIC(18,6),
    rmse NUMERIC(18,6),
    wape NUMERIC(18,6),
    bias NUMERIC(18,6),
    sample_count INTEGER NOT NULL DEFAULT 0,
    absolute_error_sum NUMERIC(24,6) NOT NULL DEFAULT 0,
    actual_sum NUMERIC(24,6) NOT NULL DEFAULT 0,
    forecast_sum NUMERIC(24,6) NOT NULL DEFAULT 0,
    UNIQUE (model_run_id, warehouse_id, sku_id)
);

CREATE TABLE IF NOT EXISTS replenishment_recommendations (
    recommendation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id BIGINT NOT NULL REFERENCES model_runs(model_run_id),
    recommendation_date DATE NOT NULL,
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    supplier_id BIGINT REFERENCES dim_supplier(supplier_id),
    service_level NUMERIC(6,5) NOT NULL CHECK (service_level > 0 AND service_level < 1),
    avg_daily_demand NUMERIC(18,6) NOT NULL CHECK (avg_daily_demand >= 0),
    demand_stddev NUMERIC(18,6) NOT NULL CHECK (demand_stddev >= 0),
    avg_lead_time_days NUMERIC(10,4) NOT NULL CHECK (avg_lead_time_days >= 0),
    lead_time_stddev NUMERIC(10,4) NOT NULL CHECK (lead_time_stddev >= 0),
    safety_stock_qty NUMERIC(18,6) NOT NULL CHECK (safety_stock_qty >= 0),
    reorder_point_qty NUMERIC(18,6) NOT NULL CHECK (reorder_point_qty >= 0),
    target_stock_qty NUMERIC(18,6) NOT NULL CHECK (target_stock_qty >= 0),
    inventory_position_qty NUMERIC(18,6) NOT NULL,
    gross_recommended_order_qty NUMERIC(18,6) NOT NULL CHECK (gross_recommended_order_qty >= 0),
    recommended_order_qty NUMERIC(18,6) NOT NULL CHECK (recommended_order_qty >= 0),
    expected_stockout_date DATE,
    risk_band VARCHAR(20) NOT NULL CHECK (risk_band IN ('CRITICAL','HIGH','MEDIUM','LOW')),
    calculation_details JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (model_run_id, recommendation_date, warehouse_id, sku_id)
);


CREATE TABLE IF NOT EXISTS inventory_transfer_recommendations (
    transfer_recommendation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_run_id BIGINT NOT NULL REFERENCES model_runs(model_run_id),
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    from_warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    to_warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    transfer_qty NUMERIC(18,6) NOT NULL CHECK (transfer_qty > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED','APPROVED','REJECTED','EXECUTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (from_warehouse_id <> to_warehouse_id),
    UNIQUE (model_run_id, sku_id, from_warehouse_id, to_warehouse_id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    purchase_order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purchase_order_no VARCHAR(100) NOT NULL UNIQUE,
    supplier_id BIGINT NOT NULL REFERENCES dim_supplier(supplier_id),
    warehouse_id BIGINT NOT NULL REFERENCES dim_warehouse(warehouse_id),
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','SENT','ACKNOWLEDGED','CANCELLED','RECEIVED')),
    created_by VARCHAR(160) NOT NULL,
    approved_by VARCHAR(160),
    pdf_path TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    purchase_order_line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purchase_order_id BIGINT NOT NULL REFERENCES purchase_orders(purchase_order_id) ON DELETE CASCADE,
    sku_id BIGINT NOT NULL REFERENCES dim_sku(sku_id),
    quantity NUMERIC(18,4) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(18,4) NOT NULL CHECK (unit_price >= 0),
    recommendation_id BIGINT REFERENCES replenishment_recommendations(recommendation_id)
);

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    job_id UUID PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('FULL_PIPELINE','FORECAST','REPLENISHMENT','INGEST_CSV','OVERRIDE_RECALC','INGEST_DOCUMENT','INGEST_EXTERNAL_SIGNAL')),
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    requested_by VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    error_message TEXT,
    result JSONB
);

CREATE INDEX IF NOT EXISTS ix_inventory_transactions_sku_wh_ts
    ON inventory_transactions (sku_id, warehouse_id, transaction_ts DESC);
CREATE INDEX IF NOT EXISTS ix_inventory_snapshots_sku_wh_ts
    ON inventory_snapshots (sku_id, warehouse_id, snapshot_ts DESC);
CREATE INDEX IF NOT EXISTS ix_lead_time_supplier_wh_sku
    ON supplier_lead_time_events (supplier_id, warehouse_id, sku_id, order_date DESC);
CREATE INDEX IF NOT EXISTS ix_forecast_sku_wh_date
    ON demand_forecasts (sku_id, warehouse_id, forecast_date);
CREATE INDEX IF NOT EXISTS ix_recommendation_date_risk
    ON replenishment_recommendations (recommendation_date DESC, risk_band);
CREATE INDEX IF NOT EXISTS ix_overrides_active
    ON operational_overrides (warehouse_id, sku_id, effective_from, effective_to, status);
CREATE INDEX IF NOT EXISTS ix_jobs_status_priority
    ON pipeline_jobs (status, priority, created_at);

CREATE TABLE IF NOT EXISTS dim_date (
    date_value DATE PRIMARY KEY,
    date_key INTEGER NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

INSERT INTO dim_date
    (date_value, date_key, year, quarter, month_number, month_name, week_of_year,
     day_of_month, day_of_week, day_name, is_weekend)
SELECT
    d::DATE,
    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
    EXTRACT(YEAR FROM d)::INTEGER,
    EXTRACT(QUARTER FROM d)::INTEGER,
    EXTRACT(MONTH FROM d)::INTEGER,
    TO_CHAR(d, 'FMMonth'),
    EXTRACT(WEEK FROM d)::INTEGER,
    EXTRACT(DAY FROM d)::INTEGER,
    EXTRACT(ISODOW FROM d)::INTEGER,
    TO_CHAR(d, 'FMDay'),
    EXTRACT(ISODOW FROM d) IN (6, 7)
FROM generate_series(DATE '2020-01-01', DATE '2035-12-31', INTERVAL '1 day') AS d
ON CONFLICT (date_value) DO NOTHING;

CREATE TABLE IF NOT EXISTS raw_supplier_documents (
    document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_name VARCHAR(500) NOT NULL,
    file_sha256 CHAR(64) NOT NULL UNIQUE,
    supplier_id BIGINT REFERENCES dim_supplier(supplier_id),
    document_type VARCHAR(50) NOT NULL DEFAULT 'UNKNOWN',
    extracted_text TEXT,
    parsed_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    extraction_method VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PARSED','REVIEW_REQUIRED','FAILED')),
    error_message TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
