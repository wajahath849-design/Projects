CREATE TABLE IF NOT EXISTS system_logs (
    log_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL CHECK (datetime(timestamp) IS NOT NULL),
    facility_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    rack_id TEXT NOT NULL,
    source TEXT NOT NULL,
    component TEXT NOT NULL,
    log_level TEXT NOT NULL CHECK (log_level IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    event_code TEXT NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (server_id) REFERENCES servers(server_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL CHECK (datetime(timestamp) IS NOT NULL),
    facility_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    alert_type TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    observed_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved')),
    resolved_at TEXT CHECK (resolved_at IS NULL OR datetime(resolved_at) IS NOT NULL),
    CHECK (resolved_at IS NULL OR datetime(resolved_at) >= datetime(timestamp)),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (server_id) REFERENCES servers(server_id)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS maintenance_actions (
    action_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    timestamp TEXT NOT NULL CHECK (datetime(timestamp) IS NOT NULL),
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    result TEXT NOT NULL,
    performed_by_role TEXT NOT NULL CHECK (
        performed_by_role IN (
            'operations_engineer', 'network_engineer', 'facilities_engineer',
            'hardware_technician', 'application_engineer'
        )
    ),
    FOREIGN KEY (incident_id) REFERENCES uptime_incidents(incident_id),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (server_id) REFERENCES servers(server_id)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_logs_facility_timestamp
ON system_logs(facility_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_logs_server_timestamp
ON system_logs(server_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_logs_event_timestamp
ON system_logs(event_code, timestamp);

CREATE INDEX IF NOT EXISTS idx_logs_timestamp
ON system_logs(timestamp);

CREATE INDEX IF NOT EXISTS idx_logs_component_timestamp
ON system_logs(component, timestamp);

CREATE INDEX IF NOT EXISTS idx_logs_level_timestamp
ON system_logs(log_level, timestamp);

CREATE INDEX IF NOT EXISTS idx_alerts_facility_timestamp
ON alerts(facility_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_alerts_server_timestamp
ON alerts(server_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_alerts_status_severity
ON alerts(status, severity);

CREATE INDEX IF NOT EXISTS idx_actions_incident_timestamp
ON maintenance_actions(incident_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_actions_facility_timestamp
ON maintenance_actions(facility_id, timestamp);
