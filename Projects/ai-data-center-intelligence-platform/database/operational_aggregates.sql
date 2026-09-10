CREATE TABLE IF NOT EXISTS agg_facility_monthly_operations (
    facility_id TEXT NOT NULL,
    month TEXT NOT NULL CHECK (month GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
    log_count INTEGER NOT NULL CHECK (log_count >= 0),
    error_log_count INTEGER NOT NULL CHECK (error_log_count >= 0),
    critical_log_count INTEGER NOT NULL CHECK (critical_log_count >= 0),
    alert_count INTEGER NOT NULL CHECK (alert_count >= 0),
    critical_alert_count INTEGER NOT NULL CHECK (critical_alert_count >= 0),
    open_alert_count INTEGER NOT NULL CHECK (open_alert_count >= 0),
    incident_count INTEGER NOT NULL CHECK (incident_count >= 0),
    critical_incident_count INTEGER NOT NULL CHECK (critical_incident_count >= 0),
    downtime_minutes INTEGER NOT NULL CHECK (downtime_minutes >= 0),
    anomaly_count INTEGER NOT NULL CHECK (anomaly_count >= 0),
    significant_anomaly_count INTEGER NOT NULL CHECK (significant_anomaly_count >= 0),
    maintenance_action_count INTEGER NOT NULL CHECK (maintenance_action_count >= 0),
    PRIMARY KEY (facility_id, month),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

DELETE FROM agg_facility_monthly_operations;

INSERT INTO agg_facility_monthly_operations
WITH RECURSIVE months(month) AS (
    SELECT '2015-01'
    UNION ALL
    SELECT strftime('%Y-%m', date(month || '-01', '+1 month'))
    FROM months WHERE month < '2025-12'
),
facility_months AS (
    SELECT f.facility_id, m.month FROM facilities AS f CROSS JOIN months AS m
),
logs AS (
    SELECT facility_id, substr(timestamp,1,7) AS month,
        COUNT(*) AS log_count,
        SUM(log_level IN ('ERROR','CRITICAL')) AS error_log_count,
        SUM(log_level='CRITICAL') AS critical_log_count
    FROM system_logs GROUP BY facility_id, substr(timestamp,1,7)
),
alerts_grouped AS (
    SELECT facility_id, substr(timestamp,1,7) AS month,
        COUNT(*) AS alert_count,
        SUM(severity='critical') AS critical_alert_count,
        SUM(status='open') AS open_alert_count
    FROM alerts GROUP BY facility_id, substr(timestamp,1,7)
),
incidents AS (
    SELECT facility_id, substr(start_time,1,7) AS month,
        COUNT(*) AS incident_count,
        SUM(severity='critical') AS critical_incident_count,
        SUM(downtime_minutes) AS downtime_minutes
    FROM uptime_incidents GROUP BY facility_id, substr(start_time,1,7)
),
anomalies AS (
    SELECT facility_id, substr(timestamp,1,7) AS month,
        COUNT(*) AS anomaly_count,
        SUM(severity IN ('high','critical')) AS significant_anomaly_count
    FROM detected_anomalies GROUP BY facility_id, substr(timestamp,1,7)
),
actions AS (
    SELECT facility_id, substr(timestamp,1,7) AS month,
        COUNT(*) AS maintenance_action_count
    FROM maintenance_actions GROUP BY facility_id, substr(timestamp,1,7)
)
SELECT fm.facility_id, fm.month,
    COALESCE(l.log_count,0), COALESCE(l.error_log_count,0), COALESCE(l.critical_log_count,0),
    COALESCE(a.alert_count,0), COALESCE(a.critical_alert_count,0), COALESCE(a.open_alert_count,0),
    COALESCE(i.incident_count,0), COALESCE(i.critical_incident_count,0), COALESCE(i.downtime_minutes,0),
    COALESCE(d.anomaly_count,0), COALESCE(d.significant_anomaly_count,0),
    COALESCE(ma.maintenance_action_count,0)
FROM facility_months AS fm
LEFT JOIN logs AS l ON l.facility_id=fm.facility_id AND l.month=fm.month
LEFT JOIN alerts_grouped AS a ON a.facility_id=fm.facility_id AND a.month=fm.month
LEFT JOIN incidents AS i ON i.facility_id=fm.facility_id AND i.month=fm.month
LEFT JOIN anomalies AS d ON d.facility_id=fm.facility_id AND d.month=fm.month
LEFT JOIN actions AS ma ON ma.facility_id=fm.facility_id AND ma.month=fm.month;

CREATE TABLE IF NOT EXISTS agg_event_code_monthly (
    facility_id TEXT NOT NULL,
    month TEXT NOT NULL,
    component TEXT NOT NULL,
    event_code TEXT NOT NULL,
    log_level TEXT NOT NULL,
    event_count INTEGER NOT NULL CHECK (event_count >= 0),
    PRIMARY KEY (facility_id, month, component, event_code, log_level),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

DELETE FROM agg_event_code_monthly;

INSERT INTO agg_event_code_monthly
SELECT facility_id, substr(timestamp,1,7), component, event_code, log_level, COUNT(*)
FROM system_logs
GROUP BY facility_id, substr(timestamp,1,7), component, event_code, log_level;

CREATE INDEX IF NOT EXISTS idx_agg_ops_month ON agg_facility_monthly_operations(month);
CREATE INDEX IF NOT EXISTS idx_agg_events_code_month ON agg_event_code_monthly(event_code, month);
CREATE INDEX IF NOT EXISTS idx_agg_events_component_month ON agg_event_code_monthly(component, month);
