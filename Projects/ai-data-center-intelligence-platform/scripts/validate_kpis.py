"""Validate canonical KPI SQL against independent pandas calculations."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


SQL = {
    "average_pue": "SELECT AVG(pue) FROM power_metrics",
    "total_power_draw": "SELECT SUM(power_draw_kw) FROM power_metrics",
    "total_cooling_cost": "SELECT SUM(cooling_cost) FROM power_metrics",
    "total_downtime": "SELECT SUM(downtime_minutes) FROM uptime_incidents",
    "incident_count": "SELECT COUNT(DISTINCT incident_id) FROM uptime_incidents",
    "server_count": "SELECT COUNT(DISTINCT server_id) FROM servers",
    "active_server_count": "SELECT COUNT(DISTINCT server_id) FROM servers WHERE status='active'",
    "average_cpu_utilization": "SELECT AVG(cpu_utilization_pct) FROM server_metrics",
    "average_memory_utilization": "SELECT AVG(memory_utilization_pct) FROM server_metrics",
    "average_network_latency": "SELECT AVG(latency_ms) FROM network_metrics",
    "average_packet_loss": "SELECT AVG(packet_loss_pct) FROM network_metrics",
    "network_availability": "SELECT AVG(network_availability_pct) FROM network_metrics",
    "downtime_per_server": "SELECT 1.0 * (SELECT SUM(downtime_minutes) FROM uptime_incidents) / (SELECT COUNT(DISTINCT server_id) FROM servers)",
    "incident_rate": "SELECT 100.0 * COUNT(DISTINCT i.incident_id) / COUNT(DISTINCT s.server_id) FROM uptime_incidents i CROSS JOIN servers s",
    "operational_availability": """
        SELECT 100.0 * (1.0 -
            (SELECT SUM(downtime_minutes) FROM uptime_incidents) /
            (1.0 * (SELECT COUNT(DISTINCT server_id) FROM servers) *
             (julianday((SELECT MAX(timestamp) FROM server_metrics)) -
              julianday((SELECT MIN(timestamp) FROM server_metrics)) + 1) * 1440)
        )
    """,
    "yoy_pue_change": """
        WITH annual AS (
          SELECT CAST(strftime('%Y', timestamp) AS INTEGER) AS year, AVG(pue) AS value
          FROM power_metrics GROUP BY year
        )
        SELECT 100.0 * (c.value - p.value) / p.value
        FROM annual c JOIN annual p ON p.year = c.year - 1 WHERE c.year = 2025
    """,
    "yoy_cooling_cost_change": """
        WITH annual AS (
          SELECT CAST(strftime('%Y', timestamp) AS INTEGER) AS year, SUM(cooling_cost) AS value
          FROM power_metrics GROUP BY year
        )
        SELECT 100.0 * (c.value - p.value) / p.value
        FROM annual c JOIN annual p ON p.year = c.year - 1 WHERE c.year = 2025
    """,
    "yoy_downtime_change": """
        WITH annual AS (
          SELECT CAST(strftime('%Y', start_time) AS INTEGER) AS year, SUM(downtime_minutes) AS value
          FROM uptime_incidents GROUP BY year
        )
        SELECT 100.0 * (c.value - p.value) / p.value
        FROM annual c JOIN annual p ON p.year = c.year - 1 WHERE c.year = 2025
    """,
}


def pandas_values(data_dir: Path) -> dict[str, float]:
    servers = pd.read_csv(data_dir / "servers.csv")
    server_metrics = pd.read_csv(data_dir / "server_metrics.csv")
    power = pd.read_csv(data_dir / "power_metrics.csv")
    network = pd.read_csv(data_dir / "network_metrics.csv")
    incidents = pd.read_csv(data_dir / "uptime_incidents.csv")

    power_year = pd.to_datetime(power["timestamp"]).dt.year
    incident_year = pd.to_datetime(incidents["start_time"]).dt.year
    server_dates = pd.to_datetime(server_metrics["timestamp"])
    server_count = servers["server_id"].nunique()
    incident_count = incidents["incident_id"].nunique()
    downtime = incidents["downtime_minutes"].sum()
    visible_days = (server_dates.max() - server_dates.min()).days + 1

    pue_2024 = power.loc[power_year.eq(2024), "pue"].mean()
    pue_2025 = power.loc[power_year.eq(2025), "pue"].mean()
    cost_2024 = power.loc[power_year.eq(2024), "cooling_cost"].sum()
    cost_2025 = power.loc[power_year.eq(2025), "cooling_cost"].sum()
    down_2024 = incidents.loc[incident_year.eq(2024), "downtime_minutes"].sum()
    down_2025 = incidents.loc[incident_year.eq(2025), "downtime_minutes"].sum()

    return {
        "average_pue": power["pue"].mean(),
        "total_power_draw": power["power_draw_kw"].sum(),
        "total_cooling_cost": power["cooling_cost"].sum(),
        "total_downtime": downtime,
        "incident_count": incident_count,
        "server_count": server_count,
        "active_server_count": servers.loc[servers["status"].eq("active"), "server_id"].nunique(),
        "average_cpu_utilization": server_metrics["cpu_utilization_pct"].mean(),
        "average_memory_utilization": server_metrics["memory_utilization_pct"].mean(),
        "average_network_latency": network["latency_ms"].mean(),
        "average_packet_loss": network["packet_loss_pct"].mean(),
        "network_availability": network["network_availability_pct"].mean(),
        "downtime_per_server": downtime / server_count,
        "incident_rate": 100 * incident_count / server_count,
        "operational_availability": 100 * (1 - downtime / (server_count * visible_days * 1440)),
        "yoy_pue_change": 100 * (pue_2025 - pue_2024) / pue_2024,
        "yoy_cooling_cost_change": 100 * (cost_2025 - cost_2024) / cost_2024,
        "yoy_downtime_change": 100 * (down_2025 - down_2024) / down_2024,
    }


def validate(database: Path, data_dir: Path) -> dict[str, object]:
    expected = pandas_values(data_dir)
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        sql_values = {name: connection.execute(query).fetchone()[0] for name, query in SQL.items()}
    finally:
        connection.close()
    results = {}
    for name in SQL:
        passed = bool(np.isclose(sql_values[name], expected[name], rtol=1e-10, atol=1e-8))
        results[name] = {
            "sql_value": float(sql_values[name]),
            "python_value": float(expected[name]),
            "absolute_difference": float(abs(sql_values[name] - expected[name])),
            "passed": passed,
        }
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": database.as_posix(),
        "source_data": data_dir.as_posix(),
        "all_passed": all(item["passed"] for item in results.values()),
        "metrics": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate shared KPI definitions.")
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output", type=Path, default=Path("docs/step6_kpi_validation.json"))
    args = parser.parse_args()
    report = validate(args.database, args.data_dir)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["all_passed"] else 1)


if __name__ == "__main__":
    main()
