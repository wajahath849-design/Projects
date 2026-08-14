CREATE VIEW vw_facility_daily_performance AS
SELECT
    f.facility_id,
    f.facility_name,
    f.city,
    f.country,
    f.region,
    p.timestamp AS metric_date,
    p.power_draw_kw,
    p.it_load_kw,
    p.cooling_power_kw,
    p.pue,
    p.cooling_cost,
    n.bandwidth_utilization_pct,
    n.latency_ms,
    n.packet_loss_pct,
    n.throughput_mbps,
    n.network_availability_pct
FROM facilities AS f
JOIN power_metrics AS p ON p.facility_id = f.facility_id
JOIN network_metrics AS n
  ON n.facility_id = p.facility_id
 AND n.timestamp = p.timestamp;

CREATE VIEW vw_monthly_energy_summary AS
SELECT
    p.facility_id,
    f.facility_name,
    substr(p.timestamp, 1, 7) AS year_month,
    AVG(p.pue) AS average_pue,
    SUM(p.power_draw_kw) AS total_power_draw_kw,
    SUM(p.it_load_kw) AS total_it_load_kw,
    SUM(p.cooling_power_kw) AS total_cooling_power_kw,
    SUM(p.cooling_cost) AS total_cooling_cost
FROM power_metrics AS p
JOIN facilities AS f ON f.facility_id = p.facility_id
GROUP BY p.facility_id, f.facility_name, substr(p.timestamp, 1, 7);

CREATE VIEW vw_server_utilization AS
SELECT
    sm.metric_id,
    sm.timestamp AS metric_date,
    s.server_id,
    s.rack_id,
    s.server_type,
    s.status AS server_status,
    f.facility_id,
    f.facility_name,
    f.region,
    sm.cpu_utilization_pct,
    sm.memory_utilization_pct,
    sm.disk_utilization_pct,
    sm.network_utilization_pct
FROM server_metrics AS sm
JOIN servers AS s ON s.server_id = sm.server_id
JOIN facilities AS f ON f.facility_id = s.facility_id;

CREATE VIEW vw_incident_summary AS
SELECT
    i.incident_id,
    i.facility_id,
    f.facility_name,
    f.region,
    i.server_id,
    s.server_type,
    i.start_time,
    i.end_time,
    date(i.start_time) AS incident_date,
    i.downtime_minutes,
    i.severity,
    i.root_cause,
    i.status
FROM uptime_incidents AS i
JOIN facilities AS f ON f.facility_id = i.facility_id
JOIN servers AS s ON s.server_id = i.server_id;

CREATE VIEW vw_facility_reliability AS
SELECT
    f.facility_id,
    f.facility_name,
    f.region,
    COUNT(DISTINCT s.server_id) AS server_count,
    COUNT(DISTINCT i.incident_id) AS incident_count,
    COALESCE(SUM(i.downtime_minutes), 0) AS total_downtime_minutes,
    CASE
        WHEN COUNT(DISTINCT s.server_id) = 0 THEN NULL
        ELSE 1.0 * COALESCE(SUM(i.downtime_minutes), 0) / COUNT(DISTINCT s.server_id)
    END AS downtime_minutes_per_server
FROM facilities AS f
LEFT JOIN servers AS s ON s.facility_id = f.facility_id
LEFT JOIN uptime_incidents AS i ON i.facility_id = f.facility_id AND i.server_id = s.server_id
GROUP BY f.facility_id, f.facility_name, f.region;

