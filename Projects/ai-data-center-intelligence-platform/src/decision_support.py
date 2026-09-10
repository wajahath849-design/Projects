"""Governed facility prioritization and explicitly labelled scenario analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.database import connect_read_only
from src.forecasting import METRICS, MetricForecaster


@dataclass(frozen=True)
class DecisionSupportResult:
    priority_facility: str
    decision_confidence: str
    answer: str
    ranking: pd.DataFrame
    evidence: list[dict[str, object]]


@dataclass(frozen=True)
class ScenarioResult:
    answer: str
    frame: pd.DataFrame
    assumption: dict[str, object]
    evidence: list[dict[str, object]]


class FacilityDecisionSupport:
    def __init__(
        self,
        database_path: Path | str,
        weights_path: Path | str,
    ) -> None:
        self.database_path = Path(database_path)
        self.config = yaml.safe_load(Path(weights_path).read_text(encoding="utf-8"))
        if abs(sum(self.config["weights"].values()) - 1.0) > 1e-9:
            raise ValueError("Decision-support weights must sum to one")

    @staticmethod
    def _burden(series: pd.Series) -> pd.Series:
        minimum, maximum = float(series.min()), float(series.max())
        if abs(maximum - minimum) < 1e-12:
            return pd.Series(50.0, index=series.index)
        return 100 * (series - minimum) / (maximum - minimum)

    def rank_efficiency_upgrades(self) -> DecisionSupportResult:
        with connect_read_only(self.database_path) as connection:
            year = connection.execute("SELECT MAX(year) FROM agg_facility_yearly").fetchone()[0]
            frame = pd.read_sql_query(
                """SELECT a.facility_id, f.facility_name, a.year,
                    a.average_pue, a.total_cooling_cost,
                    a.total_downtime_minutes * 1.0 / COUNT(DISTINCT s.server_id) AS downtime_per_server,
                    a.incident_count * 100.0 / COUNT(DISTINCT s.server_id) AS incident_rate_per_100_servers,
                    (SELECT COUNT(*) FROM detected_anomalies AS d
                     WHERE d.facility_id=a.facility_id
                       AND CAST(substr(d.timestamp,1,4) AS INTEGER)=a.year) AS anomaly_count
                FROM agg_facility_yearly AS a
                JOIN facilities AS f ON f.facility_id=a.facility_id
                JOIN servers AS s ON s.facility_id=a.facility_id
                WHERE a.year=?
                GROUP BY a.facility_id, f.facility_name, a.year""",
                connection,
                params=(year,),
            )
            history = pd.read_sql_query(
                """SELECT facility_id, year, average_pue
                FROM agg_facility_yearly WHERE year <= ?
                ORDER BY facility_id, year""",
                connection,
                params=(year,),
            )
        trends, projections = {}, {}
        target_year = int(year) + 5
        for facility_id, group in history.groupby("facility_id"):
            slope, intercept = np.polyfit(
                group["year"].to_numpy(dtype=float),
                group["average_pue"].to_numpy(dtype=float),
                1,
            )
            trends[facility_id] = float(slope)
            projections[facility_id] = float(intercept + slope * target_year)
        frame["pue_trend_per_year"] = frame["facility_id"].map(trends)
        frame["pue_five_year_projection"] = frame["facility_id"].map(projections)
        weights = self.config["weights"]
        contribution_columns = []
        for metric, weight in weights.items():
            normalized = self._burden(frame[metric])
            column = f"{metric}_contribution"
            frame[column] = normalized * weight
            contribution_columns.append(column)
        frame["priority_score"] = frame[contribution_columns].sum(axis=1).round(2)
        frame = frame.sort_values(["priority_score", "facility_name"], ascending=[False, True]).reset_index(drop=True)
        frame.insert(0, "priority_rank", range(1, len(frame) + 1))
        top = frame.iloc[0]
        margin = float(top["priority_score"] - frame.iloc[1]["priority_score"])
        confidence = "High" if margin >= 15 else "Moderate" if margin >= 5 else "Low"
        factors = sorted(
            (
                (metric, float(top[f"{metric}_contribution"]))
                for metric in weights
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:3]
        factor_text = "; ".join(
            f"{name.replace('_', ' ')} contribution {value:.1f} points"
            for name, value in factors
        )
        answer = (
            f"Priority candidate: {top['facility_name']} with a governed priority score of "
            f"{top['priority_score']:.2f}/100. The main supporting factors are {factor_text}. "
            f"Decision confidence is {confidence.lower()} because the lead over the next facility is "
            f"{margin:.2f} points. This is decision support from synthetic operational indicators, "
            "not an automatic investment decision."
        )
        evidence = [{
            "kind": "decision_weights",
            "source": "analytics/decision_support_weights.yaml",
            "version": self.config["version"],
            "weights": weights,
            "source_year": int(year),
            "projection_year": target_year,
        }]
        return DecisionSupportResult(
            priority_facility=str(top["facility_name"]),
            decision_confidence=confidence,
            answer=answer,
            ranking=frame,
            evidence=evidence,
        )


class ScenarioEngine:
    METRIC_MAP = {
        "average_pue": ("average_pue", "PUE", "ratio", "lower"),
        "power_draw_kw": ("average_power_draw_kw", "Average Power Draw", "kW", "lower"),
        "it_load_kw": ("average_it_load_kw", "Average IT Load", "kW", "context"),
        "cooling_power_kw": ("average_cooling_power_kw", "Cooling Power", "kW", "lower"),
        "cooling_cost": ("total_cooling_cost", "Cooling Cost", "currency-equivalent", "lower"),
        "cpu_utilization_pct": ("average_cpu_utilization_pct", "CPU Utilization", "%", "context"),
        "memory_utilization_pct": ("average_memory_utilization_pct", "Memory Utilization", "%", "context"),
        "disk_utilization_pct": ("average_disk_utilization_pct", "Disk Utilization", "%", "lower"),
        "server_network_utilization_pct": ("average_server_network_utilization_pct", "Server Network Utilization", "%", "context"),
        "bandwidth_utilization_pct": ("average_bandwidth_utilization_pct", "Bandwidth Utilization", "%", "context"),
        "latency_ms": ("average_latency_ms", "Network Latency", "ms", "lower"),
        "packet_loss_pct": ("average_packet_loss_pct", "Packet Loss", "%", "lower"),
        "throughput_mbps": ("average_throughput_mbps", "Network Throughput", "Mbps", "higher"),
        "network_availability_pct": ("average_network_availability_pct", "Network Availability", "%", "higher"),
        "downtime_minutes": ("total_downtime_minutes", "Annual Downtime", "minutes", "lower"),
        "incident_count": ("incident_count", "Annual Incident Count", "incidents", "lower"),
    }

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)
        self.forecaster = MetricForecaster(database_path)

    @classmethod
    def preferred_direction(cls, metric_key: str) -> str:
        if metric_key not in cls.METRIC_MAP:
            raise ValueError(f"Unsupported scenario metric: {metric_key}")
        return cls.METRIC_MAP[metric_key][3]

    def run(
        self,
        metric_key: str,
        change_pct: float,
        facilities: list[str] | None = None,
        baseline_year: int | None = None,
    ) -> ScenarioResult:
        if metric_key not in self.METRIC_MAP:
            raise ValueError(f"Unsupported scenario metric: {metric_key}")
        if not -90 <= float(change_pct) <= 500:
            raise ValueError("Scenario change must be between -90% and +500%")
        aggregate_column, display_name, unit, preferred = self.METRIC_MAP[metric_key]
        latest = self.forecaster.latest_complete_year()
        year = baseline_year or latest
        evidence: list[dict[str, object]] = []
        if year <= latest:
            with connect_read_only(self.database_path) as connection:
                clauses, parameters = ["a.year=?"], [year]
                if facilities:
                    placeholders = ",".join("?" for _ in facilities)
                    clauses.append(f"f.facility_name IN ({placeholders})")
                    parameters.extend(facilities)
                sql = f"""SELECT f.facility_name, a.year AS baseline_year,
                    a.{aggregate_column} AS baseline_value
                FROM agg_facility_yearly AS a
                JOIN facilities AS f ON f.facility_id=a.facility_id
                WHERE {' AND '.join(clauses)} ORDER BY f.facility_name"""
                frame = pd.read_sql_query(sql, connection, params=parameters)
            baseline_type = "historical_fact"
            evidence.append({"kind": baseline_type, "source": "agg_facility_yearly", "sql": sql})
        else:
            spec = next(spec for spec in METRICS if spec.key == metric_key)
            forecast = self.forecaster.forecast(spec, year, facilities)
            frame = forecast.frame[forecast.frame["facility_name"] != "All Facilities"][
                ["facility_name", "forecast_year", "predicted_value"]
            ].rename(columns={"forecast_year": "baseline_year", "predicted_value": "baseline_value"})
            baseline_type = "forecast"
            evidence.append({
                "kind": baseline_type,
                "source": spec.table,
                "method": "annual_linear_trend",
                "training_end_year": forecast.training_end_year,
            })
        if frame.empty:
            raise LookupError("No baseline rows matched the scenario scope")
        frame["metric"] = display_name
        frame["unit"] = unit
        frame["baseline_type"] = baseline_type
        frame["assumption_change_pct"] = float(change_pct)
        frame["scenario_value"] = frame["baseline_value"] * (1 + float(change_pct) / 100)
        metric_spec = next(spec for spec in METRICS if spec.key == metric_key)
        frame["scenario_value"] = frame["scenario_value"].clip(
            lower=metric_spec.lower_bound,
            upper=metric_spec.upper_bound,
        )
        frame["calculated_difference"] = frame["scenario_value"] - frame["baseline_value"]
        for column in ("baseline_value", "scenario_value", "calculated_difference"):
            frame[column] = frame[column].round(4)
        sign = "+" if change_pct >= 0 else ""
        impact = (
            "directionally improves this lower-is-better metric"
            if preferred == "lower" and change_pct < 0
            else "directionally worsens this lower-is-better metric"
            if preferred == "lower" and change_pct > 0
            else "directionally improves this higher-is-better metric"
            if preferred == "higher" and change_pct > 0
            else "directionally worsens this higher-is-better metric"
            if preferred == "higher" and change_pct < 0
            else "changes demand; operational impact requires capacity context"
        )
        answer = (
            f"Scenario assumption: {display_name} changes by {sign}{change_pct:.1f}% from a "
            f"{baseline_type.replace('_', ' ')} baseline for {year}. The calculated scenario "
            f"{impact}. The result table separates the baseline, assumption, scenario result, and "
            "difference. This is a what-if calculation, not a forecast or observed outcome."
        )
        assumption = {
            "metric_key": metric_key,
            "change_pct": float(change_pct),
            "baseline_year": int(year),
            "baseline_type": baseline_type,
            "preferred_direction": preferred,
            "user_supplied": True,
        }
        return ScenarioResult(answer, frame, assumption, evidence)
