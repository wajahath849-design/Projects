CREATE TABLE IF NOT EXISTS agg_facility_yearly (
    facility_id TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 1950 AND 2100),
    server_measurement_count INTEGER NOT NULL CHECK (server_measurement_count >= 0),
    average_cpu_utilization_pct REAL,
    average_memory_utilization_pct REAL,
    average_disk_utilization_pct REAL,
    average_server_network_utilization_pct REAL,
    power_measurement_count INTEGER NOT NULL CHECK (power_measurement_count >= 0),
    average_pue REAL,
    average_power_draw_kw REAL,
    average_it_load_kw REAL,
    average_cooling_power_kw REAL,
    total_cooling_cost REAL,
    network_measurement_count INTEGER NOT NULL CHECK (network_measurement_count >= 0),
    average_bandwidth_utilization_pct REAL,
    average_latency_ms REAL,
    average_packet_loss_pct REAL,
    average_throughput_mbps REAL,
    average_network_availability_pct REAL,
    incident_count INTEGER NOT NULL CHECK (incident_count >= 0),
    total_downtime_minutes INTEGER NOT NULL CHECK (total_downtime_minutes >= 0),
    PRIMARY KEY (facility_id, year),
    FOREIGN KEY (facility_id) REFERENCES facilities(facility_id)
) WITHOUT ROWID;

DELETE FROM agg_facility_yearly;

INSERT INTO agg_facility_yearly (
    facility_id,
    year,
    server_measurement_count,
    average_cpu_utilization_pct,
    average_memory_utilization_pct,
    average_disk_utilization_pct,
    average_server_network_utilization_pct,
    power_measurement_count,
    average_pue,
    average_power_draw_kw,
    average_it_load_kw,
    average_cooling_power_kw,
    total_cooling_cost,
    network_measurement_count,
    average_bandwidth_utilization_pct,
    average_latency_ms,
    average_packet_loss_pct,
    average_throughput_mbps,
    average_network_availability_pct,
    incident_count,
    total_downtime_minutes
)
WITH
years AS (
    SELECT CAST(substr(timestamp, 1, 4) AS INTEGER) AS year FROM server_metrics
    UNION
    SELECT CAST(substr(timestamp, 1, 4) AS INTEGER) AS year FROM power_metrics
    UNION
    SELECT CAST(substr(timestamp, 1, 4) AS INTEGER) AS year FROM network_metrics
    UNION
    SELECT CAST(substr(start_time, 1, 4) AS INTEGER) AS year FROM uptime_incidents
),
facility_years AS (
    SELECT f.facility_id, y.year
    FROM facilities AS f
    CROSS JOIN years AS y
),
server_yearly AS (
    SELECT
        s.facility_id,
        CAST(substr(sm.timestamp, 1, 4) AS INTEGER) AS year,
        COUNT(*) AS measurement_count,
        AVG(sm.cpu_utilization_pct) AS average_cpu_utilization_pct,
        AVG(sm.memory_utilization_pct) AS average_memory_utilization_pct,
        AVG(sm.disk_utilization_pct) AS average_disk_utilization_pct,
        AVG(sm.network_utilization_pct) AS average_server_network_utilization_pct
    FROM server_metrics AS sm
    JOIN servers AS s ON s.server_id = sm.server_id
    GROUP BY s.facility_id, CAST(substr(sm.timestamp, 1, 4) AS INTEGER)
),
power_yearly AS (
    SELECT
        facility_id,
        CAST(substr(timestamp, 1, 4) AS INTEGER) AS year,
        COUNT(*) AS measurement_count,
        AVG(pue) AS average_pue,
        AVG(power_draw_kw) AS average_power_draw_kw,
        AVG(it_load_kw) AS average_it_load_kw,
        AVG(cooling_power_kw) AS average_cooling_power_kw,
        SUM(cooling_cost) AS total_cooling_cost
    FROM power_metrics
    GROUP BY facility_id, CAST(substr(timestamp, 1, 4) AS INTEGER)
),
network_yearly AS (
    SELECT
        facility_id,
        CAST(substr(timestamp, 1, 4) AS INTEGER) AS year,
        COUNT(*) AS measurement_count,
        AVG(bandwidth_utilization_pct) AS average_bandwidth_utilization_pct,
        AVG(latency_ms) AS average_latency_ms,
        AVG(packet_loss_pct) AS average_packet_loss_pct,
        AVG(throughput_mbps) AS average_throughput_mbps,
        AVG(network_availability_pct) AS average_network_availability_pct
    FROM network_metrics
    GROUP BY facility_id, CAST(substr(timestamp, 1, 4) AS INTEGER)
),
incident_yearly AS (
    SELECT
        facility_id,
        CAST(substr(start_time, 1, 4) AS INTEGER) AS year,
        COUNT(*) AS incident_count,
        SUM(downtime_minutes) AS total_downtime_minutes
    FROM uptime_incidents
    GROUP BY facility_id, CAST(substr(start_time, 1, 4) AS INTEGER)
)
SELECT
    fy.facility_id,
    fy.year,
    COALESCE(s.measurement_count, 0),
    s.average_cpu_utilization_pct,
    s.average_memory_utilization_pct,
    s.average_disk_utilization_pct,
    s.average_server_network_utilization_pct,
    COALESCE(p.measurement_count, 0),
    p.average_pue,
    p.average_power_draw_kw,
    p.average_it_load_kw,
    p.average_cooling_power_kw,
    p.total_cooling_cost,
    COALESCE(n.measurement_count, 0),
    n.average_bandwidth_utilization_pct,
    n.average_latency_ms,
    n.average_packet_loss_pct,
    n.average_throughput_mbps,
    n.average_network_availability_pct,
    COALESCE(i.incident_count, 0),
    COALESCE(i.total_downtime_minutes, 0)
FROM facility_years AS fy
LEFT JOIN server_yearly AS s
  ON s.facility_id = fy.facility_id AND s.year = fy.year
LEFT JOIN power_yearly AS p
  ON p.facility_id = fy.facility_id AND p.year = fy.year
LEFT JOIN network_yearly AS n
  ON n.facility_id = fy.facility_id AND n.year = fy.year
LEFT JOIN incident_yearly AS i
  ON i.facility_id = fy.facility_id AND i.year = fy.year
ORDER BY fy.facility_id, fy.year;
