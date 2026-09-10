"""Database-calculated monthly operations briefing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import pandas as pd

from src.database import connect_read_only
from src.decision_support import FacilityDecisionSupport
from src.forecasting import METRICS, MetricForecaster


@dataclass(frozen=True)
class OperationsBriefing:
    title: str
    answer: str
    sections: dict[str, str]
    evidence: dict[str, object]
    recommendations: pd.DataFrame


class OperationsBriefingEngine:
    def __init__(self, database_path: Path | str, project_root: Path | str) -> None:
        self.database_path = Path(database_path)
        self.project_root = Path(project_root)

    def generate(self, month: str | None = None) -> OperationsBriefing:
        with connect_read_only(self.database_path) as connection:
            selected_month = month or connection.execute(
                "SELECT MAX(substr(timestamp,1,7)) FROM power_metrics"
            ).fetchone()[0]
            if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", str(selected_month)):
                raise ValueError("Briefing month must use YYYY-MM format")
            try:
                period = pd.Period(selected_month, freq="M")
            except (TypeError, ValueError) as error:
                raise ValueError("Briefing month must use YYYY-MM format") from error
            previous_month = str(period - 1)
            power = pd.read_sql_query(
                """SELECT f.facility_name, substr(p.timestamp,1,7) AS month,
                    AVG(p.pue) AS average_pue,
                    SUM(p.cooling_cost) AS cooling_cost
                FROM power_metrics AS p JOIN facilities AS f ON f.facility_id=p.facility_id
                WHERE substr(p.timestamp,1,7) IN (?, ?)
                GROUP BY f.facility_name, substr(p.timestamp,1,7)""",
                connection,
                params=(previous_month, selected_month),
            )
            current = power[power["month"] == selected_month].set_index("facility_name")
            previous = power[power["month"] == previous_month].set_index("facility_name")
            changes = current[["average_pue"]].join(
                previous[["average_pue"]], lsuffix="_current", rsuffix="_previous"
            )
            changes["change_pct"] = 100 * (
                changes["average_pue_current"] - changes["average_pue_previous"]
            ) / changes["average_pue_previous"]
            pue_row = changes.sort_values("change_pct", ascending=False).iloc[0]
            pue_facility = changes.sort_values("change_pct", ascending=False).index[0]
            reliability = connection.execute(
                """SELECT COUNT(*) AS incident_count,
                    SUM(severity='critical') AS critical_count,
                    COALESCE(SUM(downtime_minutes),0) AS downtime_minutes
                FROM uptime_incidents WHERE substr(start_time,1,7)=?""",
                (selected_month,),
            ).fetchone()
            network = pd.read_sql_query(
                """SELECT f.facility_name, AVG(n.network_availability_pct) AS availability,
                    AVG(n.latency_ms) AS latency_ms
                FROM network_metrics AS n JOIN facilities AS f ON f.facility_id=n.facility_id
                WHERE substr(n.timestamp,1,7)=?
                GROUP BY f.facility_name ORDER BY availability DESC, f.facility_name""",
                connection,
                params=(selected_month,),
            )
            capacity = pd.read_sql_query(
                """SELECT f.facility_name, substr(sm.timestamp,1,7) AS month,
                    AVG(sm.cpu_utilization_pct) AS cpu_utilization
                FROM server_metrics AS sm
                JOIN servers AS s ON s.server_id=sm.server_id
                JOIN facilities AS f ON f.facility_id=s.facility_id
                WHERE substr(sm.timestamp,1,7) IN (?, ?)
                GROUP BY f.facility_name, substr(sm.timestamp,1,7)""",
                connection,
                params=(previous_month, selected_month),
            )
            cap_current = capacity[capacity["month"] == selected_month].set_index("facility_name")
            cap_previous = capacity[capacity["month"] == previous_month].set_index("facility_name")
            cap_change = cap_current.join(cap_previous, lsuffix="_current", rsuffix="_previous")
            cap_change["change_points"] = (
                cap_change["cpu_utilization_current"] - cap_change["cpu_utilization_previous"]
            )
            cap_row = cap_change.sort_values("change_points", ascending=False).iloc[0]
            cap_facility = cap_change.sort_values("change_points", ascending=False).index[0]
            anomaly_count = connection.execute(
                """SELECT COUNT(*) FROM detected_anomalies
                WHERE substr(timestamp,1,7)=? AND severity IN ('high','critical')""",
                (selected_month,),
            ).fetchone()[0]

        pue_spec = next(spec for spec in METRICS if spec.key == "average_pue")
        forecast = MetricForecaster(self.database_path).forecast(pue_spec, int(selected_month[:4]) + 5)
        facility_forecasts = forecast.frame[forecast.frame["facility_name"] != "All Facilities"]
        projected = facility_forecasts.sort_values("predicted_value", ascending=False).iloc[0]
        decision = FacilityDecisionSupport(
            self.database_path,
            self.project_root / "analytics/decision_support_weights.yaml",
        ).rank_efficiency_upgrades()
        recommendations = decision.ranking.head(3)[
            ["priority_rank", "facility_name", "priority_score"]
        ].copy()
        sections = {
            "ENERGY": (
                f"{pue_facility} had the largest month-over-month PUE change at "
                f"{float(pue_row['change_pct']):+.2f}% ({float(pue_row['average_pue_previous']):.3f} to "
                f"{float(pue_row['average_pue_current']):.3f})."
            ),
            "RELIABILITY": (
                f"{int(reliability['incident_count'])} incidents were recorded, including "
                f"{int(reliability['critical_count'] or 0)} critical incidents and "
                f"{int(reliability['downtime_minutes'])} downtime minutes."
            ),
            "NETWORK": (
                f"{network.iloc[0]['facility_name']} recorded the highest average network availability "
                f"at {network.iloc[0]['availability']:.4f}% with {network.iloc[0]['latency_ms']:.3f} ms latency."
            ),
            "CAPACITY": (
                f"{cap_facility} had the largest CPU utilization change at "
                f"{float(cap_row['change_points']):+.2f} percentage points."
            ),
            "ANOMALIES": f"{int(anomaly_count)} high or critical stored anomalies occurred in the month.",
            "FORECAST": (
                f"{projected['facility_name']} has the highest governed {int(selected_month[:4]) + 5} "
                f"PUE projection at {projected['predicted_value']:.4f}. This is a projection, not an observation."
            ),
        }
        recommendation_text = "; ".join(
            f"{int(row.priority_rank)}. {row.facility_name} ({row.priority_score:.2f})"
            for row in recommendations.itertuples()
        )
        answer = "\n\n".join(f"**{name}**\n\n{text}" for name, text in sections.items())
        answer += f"\n\n**RECOMMENDED INVESTIGATIONS**\n\n{recommendation_text}."
        evidence = {
            "month": selected_month,
            "previous_month": previous_month,
            "power_rows": power.to_dict("records"),
            "network_rows": network.to_dict("records"),
            "capacity_rows": capacity.to_dict("records"),
            "reliability": dict(reliability),
            "anomaly_count": int(anomaly_count),
            "forecast_method": "annual_linear_trend",
            "decision_weights": decision.evidence,
        }
        return OperationsBriefing(
            title=f"Monthly Operations Brief — {period.strftime('%B %Y')}",
            answer=answer,
            sections=sections,
            evidence=evidence,
            recommendations=recommendations,
        )
