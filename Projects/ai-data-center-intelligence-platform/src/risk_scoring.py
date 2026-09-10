"""Explainable server failure-risk screening and facility health scoring."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml


@dataclass(frozen=True)
class ScoreOutputs:
    server_risk: pd.DataFrame
    facility_health: pd.DataFrame
    metadata: dict[str, object]


class OperationsScoreEngine:
    RISK_METHOD_VERSION = "rules_v1.0.0"

    def __init__(self, connection: sqlite3.Connection, weights_path: Path | str) -> None:
        self.connection = connection
        self.weights_path = Path(weights_path)
        self.health_config = yaml.safe_load(self.weights_path.read_text(encoding="utf-8"))
        weights = self.health_config["weights"]
        if abs(sum(weights.values()) - 1.0) > 1e-9:
            raise ValueError("Health-score weights must sum to one")

    def score(self) -> ScoreOutputs:
        latest_date = self.connection.execute(
            "SELECT MAX(timestamp) FROM server_metrics"
        ).fetchone()[0]
        latest_year = int(latest_date[:4])
        server_risk = self._server_risk(latest_date)
        facility_health = self._facility_health(latest_year, latest_date)
        return ScoreOutputs(
            server_risk=server_risk,
            facility_health=facility_health,
            metadata={
                "score_date": latest_date,
                "latest_complete_year": latest_year,
                "risk_method_version": self.RISK_METHOD_VERSION,
                "health_weights_version": self.health_config["version"],
                "health_weights": self.health_config["weights"],
            },
        )

    def _server_risk(self, score_date: str) -> pd.DataFrame:
        inventory = pd.read_sql_query(
            """SELECT s.server_id, s.facility_id, f.facility_name, s.rack_id,
                s.server_type, s.install_date,
                CAST((julianday(?) - julianday(s.install_date)) / 365.25 AS REAL) AS asset_age_years
            FROM servers AS s JOIN facilities AS f ON f.facility_id=s.facility_id
            ORDER BY s.server_id""",
            self.connection,
            params=(score_date,),
        )
        utilization = pd.read_sql_query(
            """SELECT server_id,
                AVG(cpu_utilization_pct) AS avg_cpu_30d,
                AVG(memory_utilization_pct) AS avg_memory_30d,
                AVG(disk_utilization_pct) AS avg_disk_30d
            FROM server_metrics
            WHERE date(timestamp) > date(?, '-30 days') AND date(timestamp) <= date(?)
            GROUP BY server_id""",
            self.connection,
            params=(score_date, score_date),
        )
        logs = pd.read_sql_query(
            """SELECT server_id,
                SUM(event_code IN ('HW_HEALTH_WARNING','DEVICE_IO_ERROR')) AS hardware_error_count,
                SUM(event_code='SERVER_SERVICE_IMPACT') AS service_impact_count,
                SUM(event_code IN ('TEMP_HIGH','COOL_FLOW_LOW','COOLING_INCIDENT')) AS thermal_signal_count
            FROM system_logs
            WHERE date(timestamp) > date(?, '-365 days') AND date(timestamp) <= date(?)
            GROUP BY server_id""",
            self.connection,
            params=(score_date, score_date),
        )
        incidents = pd.read_sql_query(
            """SELECT server_id, COUNT(*) AS incident_count_365d,
                SUM(CASE severity WHEN 'critical' THEN 8 WHEN 'high' THEN 4
                    WHEN 'medium' THEN 2 ELSE 1 END) AS incident_severity_points
            FROM uptime_incidents
            WHERE date(start_time) > date(?, '-365 days') AND date(start_time) <= date(?)
            GROUP BY server_id""",
            self.connection,
            params=(score_date, score_date),
        )
        maintenance = pd.read_sql_query(
            """SELECT server_id, COUNT(*) AS maintenance_count_365d
            FROM maintenance_actions
            WHERE date(timestamp) > date(?, '-365 days') AND date(timestamp) <= date(?)
            GROUP BY server_id""",
            self.connection,
            params=(score_date, score_date),
        )
        frame = inventory.merge(utilization, on="server_id", how="left")
        frame = frame.merge(logs, on="server_id", how="left")
        frame = frame.merge(incidents, on="server_id", how="left")
        frame = frame.merge(maintenance, on="server_id", how="left")
        numeric = [
            "avg_cpu_30d", "avg_memory_30d", "avg_disk_30d",
            "hardware_error_count", "service_impact_count", "thermal_signal_count",
            "incident_count_365d", "incident_severity_points", "maintenance_count_365d",
        ]
        frame[numeric] = frame[numeric].fillna(0)
        frame["hardware_points"] = (frame["hardware_error_count"] * 5).clip(upper=20)
        frame["service_impact_points"] = (frame["service_impact_count"] * 5).clip(upper=15)
        frame["thermal_points"] = (frame["thermal_signal_count"] * 3).clip(upper=15)
        frame["incident_points"] = (frame["incident_severity_points"] * 2).clip(upper=20)
        frame["resource_points"] = (
            ((frame["avg_cpu_30d"] - 80).clip(lower=0) / 20 * 5)
            + ((frame["avg_memory_30d"] - 85).clip(lower=0) / 15 * 4)
            + ((frame["avg_disk_30d"] - 75).clip(lower=0) / 25 * 6)
        ).clip(upper=15)
        frame["maintenance_points"] = (frame["maintenance_count_365d"] * 1.5).clip(upper=5)
        frame["age_points"] = (((frame["asset_age_years"] - 4).clip(lower=0) / 8) * 10).clip(upper=10)
        point_columns = [
            "hardware_points", "service_impact_points", "thermal_points",
            "incident_points", "resource_points", "maintenance_points", "age_points",
        ]
        frame["risk_score"] = frame[point_columns].sum(axis=1).round(2)
        frame["risk_level"] = pd.cut(
            frame["risk_score"], bins=[-1, 24.999, 49.999, 74.999, 100],
            labels=["low", "moderate", "high", "critical"],
        ).astype(str)
        recommendations = {
            "hardware_points": "Inspect hardware health and storage/controller evidence.",
            "service_impact_points": "Review service-impact events and validate server health.",
            "thermal_points": "Inspect cooling and rack-temperature evidence.",
            "incident_points": "Review repeated incidents and confirmed resolution history.",
            "resource_points": "Review recent CPU memory and disk pressure.",
            "maintenance_points": "Review repeated maintenance and unresolved patterns.",
            "age_points": "Review lifecycle status and age-related maintenance needs.",
        }
        frame["primary_signal"] = frame[point_columns].idxmax(axis=1)
        frame["recommendation"] = frame["primary_signal"].map(recommendations)
        frame.insert(0, "risk_id", [f"RISK-{index:05d}" for index in range(1, len(frame) + 1)])
        frame["score_date"] = score_date
        frame["forecast_horizon_days"] = 7
        frame["lookback_days"] = 365
        frame["method_version"] = self.RISK_METHOD_VERSION
        frame["signal_summary_json"] = frame.apply(
            lambda row: json.dumps({
                "hardware_errors": int(row["hardware_error_count"]),
                "service_impacts": int(row["service_impact_count"]),
                "thermal_signals": int(row["thermal_signal_count"]),
                "incidents": int(row["incident_count_365d"]),
                "maintenance_actions": int(row["maintenance_count_365d"]),
                "cpu_30d": round(float(row["avg_cpu_30d"]), 2),
                "memory_30d": round(float(row["avg_memory_30d"]), 2),
                "disk_30d": round(float(row["avg_disk_30d"]), 2),
                "asset_age_years": round(float(row["asset_age_years"]), 2),
            }, sort_keys=True),
            axis=1,
        )
        return frame[[
            "risk_id", "score_date", "forecast_horizon_days", "server_id", "facility_id",
            "risk_score", "risk_level", "hardware_error_count", "service_impact_count",
            "thermal_signal_count", "incident_count_365d", "incident_severity_points",
            "maintenance_count_365d", "avg_cpu_30d", "avg_memory_30d", "avg_disk_30d",
            "asset_age_years", "primary_signal", "recommendation", "signal_summary_json",
            "lookback_days", "method_version",
        ]]

    @staticmethod
    def _relative_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
        minimum, maximum = float(series.min()), float(series.max())
        if abs(maximum - minimum) < 1e-12:
            return pd.Series(100.0, index=series.index)
        normalized = 100 * (series - minimum) / (maximum - minimum)
        return normalized if higher_is_better else 100 - normalized

    def _facility_health(self, year: int, score_date: str) -> pd.DataFrame:
        frame = pd.read_sql_query(
            """SELECT a.*, f.facility_name,
                (SELECT COUNT(*) FROM servers AS s WHERE s.facility_id=a.facility_id) AS server_count,
                (SELECT COALESCE(SUM(CASE i.severity WHEN 'critical' THEN 8 WHEN 'high' THEN 4
                    WHEN 'medium' THEN 2 ELSE 1 END), 0)
                 FROM uptime_incidents AS i WHERE i.facility_id=a.facility_id
                   AND CAST(substr(i.start_time,1,4) AS INTEGER)=a.year) AS severity_points,
                (SELECT COUNT(*) FROM detected_anomalies AS d WHERE d.facility_id=a.facility_id
                   AND CAST(substr(d.timestamp,1,4) AS INTEGER)=a.year) AS anomaly_count
            FROM agg_facility_yearly AS a
            JOIN facilities AS f ON f.facility_id=a.facility_id
            WHERE a.year=? ORDER BY a.facility_id""",
            self.connection,
            params=(year,),
        )
        frame["downtime_per_server"] = frame["total_downtime_minutes"] / frame["server_count"]
        frame["severity_points_per_server"] = frame["severity_points"] / frame["server_count"]
        frame["energy_efficiency_score"] = self._relative_score(frame["average_pue"], False)
        frame["reliability_score"] = self._relative_score(frame["downtime_per_server"], False)
        availability = self._relative_score(frame["average_network_availability_pct"], True)
        latency = self._relative_score(frame["average_latency_ms"], False)
        packet_loss = self._relative_score(frame["average_packet_loss_pct"], False)
        frame["network_health_score"] = 0.50 * availability + 0.25 * latency + 0.25 * packet_loss
        utilization = frame[[
            "average_cpu_utilization_pct", "average_memory_utilization_pct",
            "average_disk_utilization_pct",
        ]].mean(axis=1)
        frame["infrastructure_utilization_score"] = (
            100 - (utilization - 70).clip(lower=0) * (100 / 30)
        ).clip(lower=0, upper=100)
        frame["incident_severity_score"] = self._relative_score(
            frame["severity_points_per_server"], False
        )
        frame["anomaly_frequency_score"] = self._relative_score(frame["anomaly_count"], False)
        weights = self.health_config["weights"]
        component_columns = [
            "energy_efficiency_score", "reliability_score", "network_health_score",
            "infrastructure_utilization_score", "incident_severity_score",
            "anomaly_frequency_score",
        ]
        # Publish and weight the same rounded component values so the total reconciles exactly.
        frame[component_columns] = frame[component_columns].round(2)
        frame["health_score"] = (
            frame["energy_efficiency_score"] * weights["energy_efficiency"]
            + frame["reliability_score"] * weights["reliability"]
            + frame["network_health_score"] * weights["network_health"]
            + frame["infrastructure_utilization_score"] * weights["infrastructure_utilization"]
            + frame["incident_severity_score"] * weights["incident_severity"]
            + frame["anomaly_frequency_score"] * weights["anomaly_frequency"]
        ).round(2)
        frame.insert(0, "health_score_id", [f"HEALTH-{index:03d}" for index in range(1, len(frame) + 1)])
        frame["score_date"] = score_date
        frame["source_year"] = year
        frame["weights_version"] = self.health_config["version"]
        frame["weights_json"] = json.dumps(weights, sort_keys=True)
        return frame[[
            "health_score_id", "score_date", "source_year", "facility_id", "health_score",
            "energy_efficiency_score", "reliability_score", "network_health_score",
            "infrastructure_utilization_score", "incident_severity_score",
            "anomaly_frequency_score", "weights_version", "weights_json",
        ]]
