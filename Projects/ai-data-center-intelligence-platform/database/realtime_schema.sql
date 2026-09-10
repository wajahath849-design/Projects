PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS simulation_sessions (
    simulation_session_id TEXT PRIMARY KEY,
    scenario_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'paused', 'completed', 'stopped')),
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT,
    speed_multiplier REAL NOT NULL CHECK (speed_multiplier > 0 AND speed_multiplier <= 100),
    random_seed INTEGER NOT NULL,
    retention_hours INTEGER NOT NULL CHECK (retention_hours BETWEEN 1 AND 720),
    max_events INTEGER NOT NULL CHECK (max_events BETWEEN 1 AND 5000000),
    event_version INTEGER NOT NULL DEFAULT 0,
    state_version INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}'
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_metric_events (
    event_id TEXT PRIMARY KEY,
    event_timestamp TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    unit TEXT NOT NULL,
    source TEXT NOT NULL,
    quality_flag TEXT NOT NULL CHECK (quality_flag IN ('valid', 'suspect', 'interpolated')),
    simulation_session_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_log_events (
    event_id TEXT PRIMARY KEY,
    event_timestamp TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT,
    level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error', 'critical')),
    component TEXT NOT NULL,
    event_code TEXT NOT NULL,
    message TEXT NOT NULL,
    source TEXT NOT NULL,
    quality_flag TEXT NOT NULL CHECK (quality_flag IN ('valid', 'suspect', 'interpolated')),
    simulation_session_id TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_alert_events (
    alert_id TEXT PRIMARY KEY,
    event_timestamp TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT,
    metric_name TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    observed_value REAL,
    threshold_value REAL,
    status TEXT NOT NULL CHECK (status IN ('active', 'acknowledged', 'resolved')),
    source TEXT NOT NULL,
    quality_flag TEXT NOT NULL CHECK (quality_flag IN ('valid', 'suspect', 'interpolated')),
    simulation_session_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_incident_events (
    incident_event_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    ingestion_timestamp TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT,
    event_type TEXT NOT NULL CHECK (event_type IN ('opened', 'updated', 'resolved')),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL CHECK (status IN ('active', 'monitoring', 'resolved')),
    summary TEXT NOT NULL,
    source TEXT NOT NULL,
    simulation_session_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_anomalies (
    anomaly_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    anomaly_timestamp TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT,
    metric_name TEXT NOT NULL,
    observed_value REAL NOT NULL,
    expected_value REAL NOT NULL,
    lower_bound REAL,
    upper_bound REAL,
    deviation REAL NOT NULL,
    deviation_pct REAL,
    severity TEXT NOT NULL CHECK (severity IN ('medium', 'high', 'critical')),
    detection_method TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'resolved')),
    active_until TEXT NOT NULL,
    simulation_session_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES realtime_metric_events(event_id) ON DELETE CASCADE,
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_metric_state (
    simulation_session_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    server_id TEXT,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    unit TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_timestamp TEXT NOT NULL,
    quality_flag TEXT NOT NULL,
    PRIMARY KEY (simulation_session_id, facility_id, scope_key, metric_name),
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES realtime_metric_events(event_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_rolling_state (
    simulation_session_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    server_id TEXT,
    metric_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    window_minutes INTEGER NOT NULL CHECK (window_minutes IN (1, 5, 15)),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count > 0),
    mean_value REAL NOT NULL,
    min_value REAL NOT NULL,
    max_value REAL NOT NULL,
    stddev_value REAL NOT NULL,
    change_rate_per_minute REAL NOT NULL,
    baseline_deviation REAL NOT NULL,
    last_value REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (simulation_session_id, facility_id, scope_key, metric_name, window_minutes),
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS realtime_facility_health (
    simulation_session_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    score_timestamp TEXT NOT NULL,
    health_score REAL NOT NULL CHECK (health_score BETWEEN 0 AND 100),
    energy_efficiency_score REAL NOT NULL,
    reliability_score REAL NOT NULL,
    network_health_score REAL NOT NULL,
    infrastructure_score REAL NOT NULL,
    alert_score REAL NOT NULL,
    anomaly_score REAL NOT NULL,
    active_alert_count INTEGER NOT NULL,
    active_anomaly_count INTEGER NOT NULL,
    data_completeness_pct REAL NOT NULL CHECK (data_completeness_pct BETWEEN 0 AND 100),
    drivers_json TEXT NOT NULL,
    method_version TEXT NOT NULL,
    PRIMARY KEY (simulation_session_id, facility_id),
    FOREIGN KEY (simulation_session_id) REFERENCES simulation_sessions(simulation_session_id) ON DELETE CASCADE
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_rt_metric_session_time
    ON realtime_metric_events(simulation_session_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_rt_metric_scope_time
    ON realtime_metric_events(simulation_session_id, facility_id, server_id, metric_name, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_rt_log_scope_time
    ON realtime_log_events(simulation_session_id, facility_id, server_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_rt_alert_active
    ON realtime_alert_events(simulation_session_id, status, facility_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_rt_incident_active
    ON realtime_incident_events(simulation_session_id, status, facility_id, event_timestamp);
CREATE INDEX IF NOT EXISTS idx_rt_anomaly_active
    ON realtime_anomalies(simulation_session_id, status, facility_id, anomaly_timestamp);
