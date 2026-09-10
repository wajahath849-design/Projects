"""Explainable, deterministic anomaly detection over canonical operational metrics."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MethodComparison:
    method: str
    anomaly_count: int
    anomaly_rate_pct: float


class AnomalyDetector:
    """Compare simple baselines and select a seasonal IQR rule."""

    SELECTED_METHOD = "seasonal_iqr"

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def load_observations(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        frames.append(self._load_wide(
            """SELECT timestamp, facility_id, 1 AS source_record_count,
                pue, power_draw_kw, cooling_power_kw, cooling_cost
            FROM power_metrics""",
            "power_metrics",
            "facility_day",
            ["pue", "power_draw_kw", "cooling_power_kw", "cooling_cost"],
        ))
        frames.append(self._load_wide(
            """SELECT timestamp, facility_id, 1 AS source_record_count,
                latency_ms, packet_loss_pct
            FROM network_metrics""",
            "network_metrics",
            "facility_day",
            ["latency_ms", "packet_loss_pct"],
        ))
        frames.append(self._load_wide(
            """SELECT sm.timestamp, s.facility_id, COUNT(*) AS source_record_count,
                AVG(sm.cpu_utilization_pct) AS cpu_utilization_pct,
                AVG(sm.memory_utilization_pct) AS memory_utilization_pct,
                AVG(sm.disk_utilization_pct) AS disk_utilization_pct,
                AVG(sm.network_utilization_pct) AS network_utilization_pct
            FROM server_metrics AS sm
            JOIN servers AS s ON s.server_id = sm.server_id
            GROUP BY sm.timestamp, s.facility_id""",
            "server_metrics",
            "facility_day",
            [
                "cpu_utilization_pct", "memory_utilization_pct",
                "disk_utilization_pct", "network_utilization_pct",
            ],
        ))
        frames.append(self._load_incident_months())
        observations = pd.concat(frames, ignore_index=True)
        observations["timestamp"] = pd.to_datetime(observations["timestamp"])
        observations["observed_value"] = pd.to_numeric(
            observations["observed_value"], errors="raise"
        )
        return observations.sort_values(
            ["metric_name", "facility_id", "timestamp"]
        ).reset_index(drop=True)

    def _load_wide(
        self,
        sql: str,
        source_table: str,
        source_grain: str,
        metrics: list[str],
    ) -> pd.DataFrame:
        frame = pd.read_sql_query(sql, self.connection)
        frame = frame.melt(
            id_vars=["timestamp", "facility_id", "source_record_count"],
            value_vars=metrics,
            var_name="metric_name",
            value_name="observed_value",
        )
        frame["source_table"] = source_table
        frame["source_grain"] = source_grain
        return frame

    def _load_incident_months(self) -> pd.DataFrame:
        facilities = pd.read_sql_query(
            "SELECT facility_id FROM facilities ORDER BY facility_id", self.connection
        )["facility_id"].tolist()
        bounds = self.connection.execute(
            "SELECT MIN(date(start_time)), MAX(date(start_time)) FROM uptime_incidents"
        ).fetchone()
        months = pd.date_range(bounds[0][:7] + "-01", bounds[1][:7] + "-01", freq="MS")
        grid = pd.MultiIndex.from_product(
            [facilities, months], names=["facility_id", "timestamp"]
        ).to_frame(index=False)
        incidents = pd.read_sql_query(
            """SELECT facility_id, substr(start_time, 1, 7) || '-01' AS timestamp,
                COUNT(*) AS incident_count,
                COALESCE(SUM(downtime_minutes), 0) AS downtime_minutes,
                COUNT(*) AS source_record_count
            FROM uptime_incidents
            GROUP BY facility_id, substr(start_time, 1, 7)""",
            self.connection,
        )
        incidents["timestamp"] = pd.to_datetime(incidents["timestamp"])
        complete = grid.merge(incidents, on=["facility_id", "timestamp"], how="left")
        for column in ("incident_count", "downtime_minutes", "source_record_count"):
            complete[column] = complete[column].fillna(0)
        frame = complete.melt(
            id_vars=["timestamp", "facility_id", "source_record_count"],
            value_vars=["downtime_minutes", "incident_count"],
            var_name="metric_name",
            value_name="observed_value",
        )
        frame["source_table"] = "uptime_incidents"
        frame["source_grain"] = "facility_month"
        return frame

    @staticmethod
    def _apply_bounds(observations: pd.DataFrame, method: str) -> pd.DataFrame:
        frame = observations.copy()
        group_keys = ["metric_name", "facility_id"]
        if method == "seasonal_iqr":
            frame["season"] = frame["timestamp"].dt.month
            group_keys.append("season")
        grouped = frame.groupby(group_keys, observed=True)["observed_value"]
        if method in {"global_iqr", "seasonal_iqr"}:
            frame["expected_value"] = grouped.transform("median")
            q1 = grouped.transform(lambda values: values.quantile(0.25))
            q3 = grouped.transform(lambda values: values.quantile(0.75))
            spread = q3 - q1
            frame["lower_bound"] = q1 - 1.5 * spread
            frame["upper_bound"] = q3 + 1.5 * spread
            frame["robust_scale"] = (spread / 1.349).replace(0, np.nan)
        elif method == "global_zscore":
            frame["expected_value"] = grouped.transform("mean")
            spread = grouped.transform("std").replace(0, np.nan)
            frame["lower_bound"] = frame["expected_value"] - 3.0 * spread
            frame["upper_bound"] = frame["expected_value"] + 3.0 * spread
            frame["robust_scale"] = spread
        else:
            raise ValueError(f"Unsupported anomaly method: {method}")
        return frame

    def compare_methods(self, observations: pd.DataFrame) -> list[MethodComparison]:
        comparisons = []
        for method in ("global_zscore", "global_iqr", "seasonal_iqr"):
            bounded = self._apply_bounds(observations, method)
            flags = (
                (bounded["observed_value"] < bounded["lower_bound"])
                | (bounded["observed_value"] > bounded["upper_bound"])
            ) & bounded["robust_scale"].notna()
            count = int(flags.sum())
            comparisons.append(MethodComparison(
                method=method,
                anomaly_count=count,
                anomaly_rate_pct=round(100.0 * count / len(bounded), 4),
            ))
        return comparisons

    def detect(self, observations: pd.DataFrame) -> pd.DataFrame:
        frame = self._apply_bounds(observations, self.SELECTED_METHOD)
        anomalies = frame[
            (
                (frame["observed_value"] < frame["lower_bound"])
                | (frame["observed_value"] > frame["upper_bound"])
            )
            & frame["robust_scale"].notna()
        ].copy()
        anomalies["direction"] = np.where(
            anomalies["observed_value"] > anomalies["upper_bound"], "high", "low"
        )
        anomalies["anomaly_score"] = (
            (anomalies["observed_value"] - anomalies["expected_value"]).abs()
            / anomalies["robust_scale"]
        )
        anomalies["severity"] = np.select(
            [anomalies["anomaly_score"] >= 6, anomalies["anomaly_score"] >= 4],
            ["critical", "high"],
            default="medium",
        )
        denominator = anomalies["expected_value"].abs().replace(0, np.nan)
        anomalies["deviation_pct"] = (
            100.0 * (anomalies["observed_value"] - anomalies["expected_value"]) / denominator
        ).fillna(0.0)
        anomalies["method"] = self.SELECTED_METHOD
        anomalies["timestamp"] = anomalies["timestamp"].dt.strftime("%Y-%m-%d")
        anomalies = anomalies.sort_values(
            ["timestamp", "facility_id", "metric_name"]
        ).reset_index(drop=True)
        anomalies.insert(
            0,
            "anomaly_id",
            [f"ANOM-{index:07d}" for index in range(1, len(anomalies) + 1)],
        )
        for column in ("deviation_pct", "anomaly_score"):
            anomalies[column] = anomalies[column].round(6)
        return anomalies[[
            "anomaly_id", "timestamp", "facility_id", "metric_name",
            "observed_value", "expected_value", "lower_bound", "upper_bound",
            "deviation_pct", "direction", "severity", "anomaly_score", "method",
            "source_table", "source_grain", "source_record_count",
        ]]
