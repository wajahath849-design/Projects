PRAGMA foreign_keys = ON;

CREATE TABLE facilities (
    facility_id TEXT PRIMARY KEY,
    facility_name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    region TEXT NOT NULL,
    capacity_mw REAL NOT NULL CHECK (capacity_mw > 0),
    rack_capacity INTEGER NOT NULL CHECK (rack_capacity > 0),
    build_year INTEGER NOT NULL CHECK (build_year BETWEEN 1950 AND 2025),
    commission_date TEXT NOT NULL CHECK (date(commission_date) IS NOT NULL)
) WITHOUT ROWID;

CREATE TABLE servers (
    server_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    rack_id TEXT NOT NULL,
    server_type TEXT NOT NULL,
    cpu_cores INTEGER NOT NULL CHECK (cpu_cores > 0),
    memory_gb INTEGER NOT NULL CHECK (memory_gb > 0),
    install_date TEXT NOT NULL CHECK (date(install_date) IS NOT NULL),
    status TEXT NOT NULL CHECK (status IN ('active', 'maintenance', 'decommissioned')),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE TABLE server_metrics (
    metric_id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    timestamp TEXT NOT NULL CHECK (date(timestamp) IS NOT NULL),
    cpu_utilization_pct REAL NOT NULL CHECK (cpu_utilization_pct BETWEEN 0 AND 100),
    memory_utilization_pct REAL NOT NULL CHECK (memory_utilization_pct BETWEEN 0 AND 100),
    disk_utilization_pct REAL NOT NULL CHECK (disk_utilization_pct BETWEEN 0 AND 100),
    network_utilization_pct REAL NOT NULL CHECK (network_utilization_pct BETWEEN 0 AND 100),
    UNIQUE (server_id, timestamp),
    FOREIGN KEY (server_id) REFERENCES servers(server_id)
) WITHOUT ROWID;

CREATE TABLE power_metrics (
    metric_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    timestamp TEXT NOT NULL CHECK (date(timestamp) IS NOT NULL),
    power_draw_kw REAL NOT NULL CHECK (power_draw_kw >= 0),
    it_load_kw REAL NOT NULL CHECK (it_load_kw >= 0),
    cooling_power_kw REAL NOT NULL CHECK (cooling_power_kw >= 0),
    pue REAL NOT NULL CHECK (pue BETWEEN 1 AND 2),
    cooling_cost REAL NOT NULL CHECK (cooling_cost >= 0),
    CHECK (power_draw_kw >= it_load_kw),
    UNIQUE (facility_id, timestamp),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE TABLE network_metrics (
    metric_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    timestamp TEXT NOT NULL CHECK (date(timestamp) IS NOT NULL),
    bandwidth_utilization_pct REAL NOT NULL CHECK (bandwidth_utilization_pct BETWEEN 0 AND 100),
    latency_ms REAL NOT NULL CHECK (latency_ms >= 0),
    packet_loss_pct REAL NOT NULL CHECK (packet_loss_pct BETWEEN 0 AND 5),
    throughput_mbps REAL NOT NULL CHECK (throughput_mbps >= 0),
    network_availability_pct REAL NOT NULL CHECK (network_availability_pct BETWEEN 0 AND 100),
    UNIQUE (facility_id, timestamp),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

CREATE TABLE uptime_incidents (
    incident_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL,
    server_id TEXT NOT NULL,
    start_time TEXT NOT NULL CHECK (datetime(start_time) IS NOT NULL),
    end_time TEXT NOT NULL CHECK (datetime(end_time) IS NOT NULL),
    downtime_minutes INTEGER NOT NULL CHECK (downtime_minutes >= 0),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    root_cause TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'resolved'),
    CHECK (datetime(end_time) >= datetime(start_time)),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id),
    FOREIGN KEY (server_id) REFERENCES servers(server_id)
) WITHOUT ROWID;

CREATE INDEX idx_servers_facility ON servers(facility_id);
CREATE INDEX idx_servers_facility_status ON servers(facility_id, status);
CREATE INDEX idx_server_metrics_timestamp ON server_metrics(timestamp);
CREATE INDEX idx_power_metrics_timestamp ON power_metrics(timestamp);
CREATE INDEX idx_network_metrics_timestamp ON network_metrics(timestamp);
CREATE INDEX idx_incidents_facility_start ON uptime_incidents(facility_id, start_time);
CREATE INDEX idx_incidents_server_start ON uptime_incidents(server_id, start_time);
CREATE INDEX idx_incidents_severity ON uptime_incidents(severity);
CREATE INDEX idx_incidents_root_cause ON uptime_incidents(root_cause);

