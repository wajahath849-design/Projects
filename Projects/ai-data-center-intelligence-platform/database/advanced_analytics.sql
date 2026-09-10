CREATE TABLE IF NOT EXISTS detected_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL CHECK (date(timestamp) IS NOT NULL),
    facility_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    observed_value REAL NOT NULL,
    expected_value REAL NOT NULL,
    lower_bound REAL NOT NULL,
    upper_bound REAL NOT NULL,
    deviation_pct REAL NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('low', 'high')),
    severity TEXT NOT NULL CHECK (severity IN ('medium', 'high', 'critical')),
    anomaly_score REAL NOT NULL CHECK (anomaly_score >= 0),
    method TEXT NOT NULL CHECK (method = 'seasonal_iqr'),
    source_table TEXT NOT NULL,
    source_grain TEXT NOT NULL CHECK (source_grain IN ('facility_day', 'facility_month')),
    source_record_count INTEGER NOT NULL CHECK (source_record_count >= 0),
    CHECK (lower_bound <= upper_bound),
    CHECK (
        (direction = 'high' AND observed_value > upper_bound)
        OR (direction = 'low' AND observed_value < lower_bound)
    ),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_anomalies_facility_timestamp
ON detected_anomalies(facility_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_anomalies_metric_timestamp
ON detected_anomalies(metric_name, timestamp);

CREATE INDEX IF NOT EXISTS idx_anomalies_severity_timestamp
ON detected_anomalies(severity, timestamp);

CREATE TABLE IF NOT EXISTS incident_reviews (
    review_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    created_at TEXT NOT NULL CHECK (datetime(created_at) IS NOT NULL),
    review_status TEXT NOT NULL CHECK (review_status IN ('pending', 'confirmed', 'rejected')),
    ai_hypothesis TEXT NOT NULL,
    ai_confidence TEXT NOT NULL CHECK (ai_confidence IN ('Low', 'Moderate', 'High')),
    human_confirmed_root_cause TEXT,
    resolution_notes TEXT,
    reviewed_by_role TEXT,
    reviewed_at TEXT CHECK (reviewed_at IS NULL OR datetime(reviewed_at) IS NOT NULL),
    knowledge_update_status TEXT NOT NULL CHECK (
        knowledge_update_status IN ('not_eligible', 'pending_review', 'approved', 'rejected')
    ),
    simulation INTEGER NOT NULL DEFAULT 0 CHECK (simulation IN (0, 1)),
    CHECK (
        (review_status = 'pending' AND reviewed_at IS NULL AND reviewed_by_role IS NULL)
        OR (review_status IN ('confirmed', 'rejected') AND reviewed_at IS NOT NULL AND reviewed_by_role IS NOT NULL)
    ),
    CHECK (knowledge_update_status <> 'approved' OR review_status = 'confirmed'),
    FOREIGN KEY (incident_id) REFERENCES uptime_incidents(incident_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_reviews_incident_created
ON incident_reviews(incident_id, created_at);

CREATE INDEX IF NOT EXISTS idx_reviews_status_knowledge
ON incident_reviews(review_status, knowledge_update_status);

CREATE TABLE IF NOT EXISTS server_failure_risk (
    risk_id TEXT PRIMARY KEY,
    score_date TEXT NOT NULL CHECK (date(score_date) IS NOT NULL),
    forecast_horizon_days INTEGER NOT NULL CHECK (forecast_horizon_days = 7),
    server_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    risk_score REAL NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
    hardware_error_count INTEGER NOT NULL CHECK (hardware_error_count >= 0),
    service_impact_count INTEGER NOT NULL CHECK (service_impact_count >= 0),
    thermal_signal_count INTEGER NOT NULL CHECK (thermal_signal_count >= 0),
    incident_count_365d INTEGER NOT NULL CHECK (incident_count_365d >= 0),
    incident_severity_points INTEGER NOT NULL CHECK (incident_severity_points >= 0),
    maintenance_count_365d INTEGER NOT NULL CHECK (maintenance_count_365d >= 0),
    avg_cpu_30d REAL NOT NULL CHECK (avg_cpu_30d BETWEEN 0 AND 100),
    avg_memory_30d REAL NOT NULL CHECK (avg_memory_30d BETWEEN 0 AND 100),
    avg_disk_30d REAL NOT NULL CHECK (avg_disk_30d BETWEEN 0 AND 100),
    asset_age_years REAL NOT NULL CHECK (asset_age_years >= 0),
    primary_signal TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    signal_summary_json TEXT NOT NULL CHECK (json_valid(signal_summary_json)),
    lookback_days INTEGER NOT NULL CHECK (lookback_days = 365),
    method_version TEXT NOT NULL,
    UNIQUE (score_date, forecast_horizon_days, server_id),
    FOREIGN KEY (server_id) REFERENCES servers(server_id),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_risk_level_score
ON server_failure_risk(risk_level, risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_risk_facility_score
ON server_failure_risk(facility_id, risk_score DESC);

CREATE TABLE IF NOT EXISTS facility_health_scores (
    health_score_id TEXT PRIMARY KEY,
    score_date TEXT NOT NULL CHECK (date(score_date) IS NOT NULL),
    source_year INTEGER NOT NULL CHECK (source_year BETWEEN 1950 AND 2100),
    facility_id TEXT NOT NULL,
    health_score REAL NOT NULL CHECK (health_score BETWEEN 0 AND 100),
    energy_efficiency_score REAL NOT NULL CHECK (energy_efficiency_score BETWEEN 0 AND 100),
    reliability_score REAL NOT NULL CHECK (reliability_score BETWEEN 0 AND 100),
    network_health_score REAL NOT NULL CHECK (network_health_score BETWEEN 0 AND 100),
    infrastructure_utilization_score REAL NOT NULL CHECK (infrastructure_utilization_score BETWEEN 0 AND 100),
    incident_severity_score REAL NOT NULL CHECK (incident_severity_score BETWEEN 0 AND 100),
    anomaly_frequency_score REAL NOT NULL CHECK (anomaly_frequency_score BETWEEN 0 AND 100),
    weights_version TEXT NOT NULL,
    weights_json TEXT NOT NULL CHECK (json_valid(weights_json)),
    UNIQUE (score_date, facility_id),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_health_score
ON facility_health_scores(health_score DESC);
