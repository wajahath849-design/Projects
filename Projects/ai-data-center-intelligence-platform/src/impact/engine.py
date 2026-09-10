"""Statistical association and guarded quasi-experimental analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

from src.database import connect_read_only
from src.sustainability.engine import CostCarbonEngine


@dataclass(frozen=True)
class CorrelationResult:
    metric_x: str
    metric_y: str
    coefficient: float
    confidence_interval_95: tuple[float, float] | None
    sample_size: int
    window: str
    scope: str
    interpretation: str
    chart_data: pd.DataFrame


@dataclass(frozen=True)
class InterventionResult:
    method: str
    outcome_metric: str
    estimated_change: float
    unit: str
    sample_size: int
    before_window: str
    after_window: str
    scope: str
    assumptions_met: tuple[str, ...]
    assumptions_failed: tuple[str, ...]
    evidence_score: dict[str, object]
    interpretation: str
    chart_data: pd.DataFrame


class ImpactAnalysisEngine:
    """Keep descriptive, temporal, and quasi-experimental claims distinct."""

    METRIC_COLUMNS = {
        "pue": ("power_metrics", "pue", "ratio"),
        "power_draw_kw": ("power_metrics", "power_draw_kw", "kW"),
        "it_load_kw": ("power_metrics", "it_load_kw", "kW"),
        "cooling_power_kw": ("power_metrics", "cooling_power_kw", "kW"),
        "latency_ms": ("network_metrics", "latency_ms", "ms"),
        "packet_loss_pct": ("network_metrics", "packet_loss_pct", "percent"),
        "network_availability_pct": ("network_metrics", "network_availability_pct", "percent"),
    }

    def __init__(
        self,
        database_path: Path | str,
        sustainability_engine: CostCarbonEngine | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.sustainability_engine = sustainability_engine

    def _metric_frame(
        self,
        metric: str,
        *,
        facility_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if metric not in self.METRIC_COLUMNS:
            raise ValueError(f"Unsupported impact metric: {metric}")
        table, column, unit = self.METRIC_COLUMNS[metric]
        sql = f"SELECT facility_id, date(timestamp) AS date, {column} AS value FROM {table} WHERE 1=1"
        params: list[object] = []
        if facility_id:
            sql += " AND facility_id=?"
            params.append(facility_id)
        if start_date:
            sql += " AND date(timestamp)>=date(?)"
            params.append(start_date)
        if end_date:
            sql += " AND date(timestamp)<=date(?)"
            params.append(end_date)
        sql += " ORDER BY date, facility_id"
        with connect_read_only(self.database_path) as connection:
            frame = pd.read_sql_query(sql, connection, params=params)
        frame["date"] = pd.to_datetime(frame["date"])
        frame.attrs["unit"] = unit
        return frame

    def correlation(
        self,
        metric_x: str,
        metric_y: str,
        *,
        facility_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> CorrelationResult:
        left = self._metric_frame(metric_x, facility_id=facility_id, start_date=start_date, end_date=end_date)
        right = self._metric_frame(metric_y, facility_id=facility_id, start_date=start_date, end_date=end_date)
        frame = left.merge(right, on=["facility_id", "date"], suffixes=("_x", "_y"), validate="one_to_one").dropna()
        n = len(frame)
        if n < 3 or frame["value_x"].nunique() < 2 or frame["value_y"].nunique() < 2:
            raise ValueError("At least three paired, varying observations are required")
        coefficient = float(frame["value_x"].corr(frame["value_y"]))
        interval = self._fisher_interval(coefficient, n)
        scope = facility_id or "all facilities pooled at facility-day grain"
        return CorrelationResult(
            metric_x, metric_y, coefficient, interval, n,
            f"{frame['date'].min().date()} to {frame['date'].max().date()}", scope,
            f"The two metrics have a {self._strength(coefficient)} association in this window. Correlation does not establish causation.",
            frame.rename(columns={"value_x": metric_x, "value_y": metric_y}),
        )

    def lead_lag(
        self,
        leading_metric: str,
        outcome_metric: str,
        *,
        facility_id: str,
        max_lag_days: int = 7,
    ) -> pd.DataFrame:
        if not 1 <= max_lag_days <= 30:
            raise ValueError("Lead-lag range must be 1 to 30 days")
        left = self._metric_frame(leading_metric, facility_id=facility_id)
        right = self._metric_frame(outcome_metric, facility_id=facility_id)
        base = left.merge(right, on=["facility_id", "date"], suffixes=("_leading", "_outcome"), validate="one_to_one")
        rows: list[dict[str, object]] = []
        for lag in range(-max_lag_days, max_lag_days + 1):
            paired = pd.DataFrame({
                "leading": base["value_leading"],
                "outcome": base["value_outcome"].shift(-lag),
            }).dropna()
            coefficient = paired["leading"].corr(paired["outcome"])
            rows.append({
                "lag_days": lag,
                "coefficient": None if pd.isna(coefficient) else float(coefficient),
                "sample_size": len(paired),
                "interpretation": "Positive lag means the leading metric is observed before the outcome; this is temporal association, not causation.",
            })
        return pd.DataFrame(rows)

    def incident_impact(self, incident_id: str, window_days: int = 7) -> dict[str, object]:
        if not 1 <= window_days <= 30:
            raise ValueError("Incident window must be 1 to 30 days")
        with connect_read_only(self.database_path) as connection:
            incident = connection.execute(
                "SELECT * FROM uptime_incidents WHERE incident_id=?", (incident_id,)
            ).fetchone()
            if incident is None:
                raise LookupError(f"Incident not found: {incident_id}")
            affected_servers = connection.execute(
                """SELECT COUNT(DISTINCT server_id) FROM uptime_incidents
                WHERE facility_id=? AND date(start_time)=date(?)""",
                (incident["facility_id"], incident["start_time"]),
            ).fetchone()[0]
        incident_day = pd.Timestamp(str(incident["start_time"])).normalize()
        start = incident_day - timedelta(days=window_days)
        end = incident_day + timedelta(days=window_days)
        metrics = []
        for metric in ("pue", "power_draw_kw", "latency_ms", "packet_loss_pct", "network_availability_pct"):
            frame = self._metric_frame(metric, facility_id=incident["facility_id"], start_date=str(start.date()), end_date=str(end.date()))
            before = frame[frame["date"] < incident_day]["value"]
            during = frame[frame["date"] == incident_day]["value"]
            after = frame[frame["date"] > incident_day]["value"]
            if before.empty or during.empty or after.empty:
                continue
            baseline = float(before.mean())
            during_value = float(during.mean())
            after_value = float(after.mean())
            recovery_rows = frame[frame["date"] > incident_day].copy()
            tolerance = max(abs(baseline) * 0.10, 1e-9)
            recovered = recovery_rows[(recovery_rows["value"] - baseline).abs() <= tolerance]
            recovery_days = None if recovered.empty else int((recovered.iloc[0]["date"] - incident_day).days)
            metrics.append({
                "metric": metric, "unit": frame.attrs.get("unit"),
                "before_mean": baseline, "during_value": during_value,
                "after_mean": after_value, "during_change_pct": self._pct_change(during_value, baseline),
                "after_change_pct": self._pct_change(after_value, baseline),
                "recovery_days": recovery_days,
            })
        cost_impact: dict[str, float] = {}
        if self.sustainability_engine is not None:
            daily = self.sustainability_engine.daily_model(str(start.date()), str(incident_day.date()), [incident["facility_id"]])
            prior = daily[daily["timestamp"] < incident_day]
            current = daily[daily["timestamp"] == incident_day]
            if not prior.empty and not current.empty:
                cost_impact = {
                    "estimated_excess_energy_kwh": float(current["modeled_energy_kwh"].mean() - prior["modeled_energy_kwh"].mean()),
                    "estimated_excess_cost_usd": float(current["modeled_energy_cost_usd"].mean() - prior["modeled_energy_cost_usd"].mean()),
                    "estimated_excess_carbon_tonnes": float(current["modeled_carbon_tonnes"].mean() - prior["modeled_carbon_tonnes"].mean()),
                }
        return {
            "incident_id": incident_id,
            "facility_id": incident["facility_id"],
            "server_id": incident["server_id"],
            "severity": incident["severity"],
            "recorded_root_cause": incident["root_cause"],
            "duration_minutes": incident["downtime_minutes"],
            "affected_servers_same_facility_day": int(affected_servers),
            "comparison_window_days": window_days,
            "metrics": metrics,
            "modeled_cost_energy_carbon_impact": cost_impact,
            "claim_level": "descriptive_before_during_after",
            "caveat": "Changes around the incident are descriptive associations; the design does not isolate causal effects.",
        }

    def intervention(
        self,
        outcome_metric: str,
        intervention_date: str,
        *,
        treated_facility_id: str,
        comparison_facility_id: str | None = None,
        window_days: int = 60,
    ) -> InterventionResult:
        if not 14 <= window_days <= 365:
            raise ValueError("Intervention window must be between 14 and 365 days")
        anchor = pd.Timestamp(intervention_date)
        start = anchor - timedelta(days=window_days)
        end = anchor + timedelta(days=window_days)
        treated = self._metric_frame(outcome_metric, facility_id=treated_facility_id, start_date=str(start.date()), end_date=str(end.date()))
        treated["period"] = np.where(treated["date"] < anchor, "before", "after")
        before = treated[treated["period"] == "before"]
        after = treated[treated["period"] == "after"]
        met: list[str] = []
        failed: list[str] = []
        if len(before) >= 30 and len(after) >= 30:
            met.append("At least 30 treated observations exist on each side of the intervention.")
        else:
            failed.append("Fewer than 30 treated observations exist on one side of the intervention.")
        method = "descriptive_before_after"
        estimate = float(after["value"].mean() - before["value"].mean()) if not before.empty and not after.empty else math.nan
        chart = treated[["date", "facility_id", "value", "period"]].copy()
        comparison_design = 0
        pretrend_support = 0
        if comparison_facility_id:
            control = self._metric_frame(outcome_metric, facility_id=comparison_facility_id, start_date=str(start.date()), end_date=str(end.date()))
            control["period"] = np.where(control["date"] < anchor, "before", "after")
            merged_pre = before.merge(
                control[control["period"] == "before"], on="date", suffixes=("_treated", "_control")
            )
            pre_corr = merged_pre["value_treated"].corr(merged_pre["value_control"]) if len(merged_pre) >= 14 else np.nan
            if len(merged_pre) >= 14 and pd.notna(pre_corr) and float(pre_corr) >= 0.7:
                method = "difference_in_differences"
                control_before = control[control["period"] == "before"]["value"].mean()
                control_after = control[control["period"] == "after"]["value"].mean()
                estimate = float((after["value"].mean() - before["value"].mean()) - (control_after - control_before))
                met.append(f"Comparison pre-period correlation is {float(pre_corr):.3f}.")
                comparison_design = 100
                pretrend_support = 100
            else:
                failed.append("Comparison facility did not meet the pre-period similarity guardrail (correlation >= 0.70 with at least 14 pairs).")
            chart = pd.concat([chart, control.assign(period=control["period"])[["date", "facility_id", "value", "period"]]])
        elif len(before) >= 30 and len(after) >= 30:
            method = "interrupted_time_series_association"
            before_slope = float(np.polyfit(np.arange(len(before)), before["value"], 1)[0])
            after_slope = float(np.polyfit(np.arange(len(after)), after["value"], 1)[0])
            estimate = after_slope - before_slope
            met.append("Segmented pre/post slopes were estimable from at least 30 points each.")
        else:
            failed.append("No credible comparison group or sufficiently long segmented series was available.")
        complete_expected = min(1.0, len(treated) / max(1, window_days * 2))
        evidence_score = {
            "data_completeness": round(100 * complete_expected),
            "temporal_ordering": 100,
            "comparison_design": comparison_design,
            "pretrend_support": pretrend_support,
            "measured_confounder_control": 0,
            "overall_qualitative": (
                "moderate" if method == "difference_in_differences" else
                "limited" if method == "interrupted_time_series_association" else "weak"
            ),
            "not_a_probability": True,
        }
        return InterventionResult(
            method, outcome_metric, estimate, self.METRIC_COLUMNS[outcome_metric][2], len(chart),
            f"{start.date()} to {(anchor - timedelta(days=1)).date()}",
            f"{anchor.date()} to {end.date()}",
            f"treated={treated_facility_id}; comparison={comparison_facility_id or 'none'}",
            tuple(met), tuple(failed), evidence_score,
            (
                "The estimate is a guarded quasi-experimental association and is not described as causal; "
                "unmeasured operational changes may explain part or all of it."
            ),
            chart,
        )

    @staticmethod
    def _fisher_interval(coefficient: float, sample_size: int) -> tuple[float, float] | None:
        if sample_size <= 3 or abs(coefficient) >= 1:
            return None
        z = math.atanh(coefficient)
        margin = NormalDist().inv_cdf(0.975) / math.sqrt(sample_size - 3)
        return math.tanh(z - margin), math.tanh(z + margin)

    @staticmethod
    def _strength(value: float) -> str:
        magnitude = abs(value)
        label = "strong" if magnitude >= 0.7 else "moderate" if magnitude >= 0.4 else "weak"
        direction = "positive" if value > 0 else "negative"
        return f"{label} {direction}"

    @staticmethod
    def _pct_change(value: float, baseline: float) -> float | None:
        return None if baseline == 0 else 100 * (value - baseline) / abs(baseline)
