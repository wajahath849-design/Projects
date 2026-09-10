from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.forecasting import AGGREGATE_COLUMNS, METRICS
from src.query_router import RouteDecision


COUNT_COLUMNS = {
    "server_metrics": "server_measurement_count",
    "power_metrics": "power_measurement_count",
    "network_metrics": "network_measurement_count",
}


@dataclass(frozen=True)
class TemplateQuery:
    sql: str
    parameters: tuple[object, ...]
    route: RouteDecision
    display_name: str
    unit: str


class QueryTemplateEngine:
    """Build allow-listed parameterized SQL over the governed yearly aggregate."""

    def __init__(self) -> None:
        self.metrics = {metric.key: metric for metric in METRICS}

    @staticmethod
    def _where(decision: RouteDecision) -> tuple[str, tuple[object, ...]]:
        clauses = []
        parameters: list[object] = []
        if decision.years:
            placeholders = ", ".join("?" for _ in decision.years)
            clauses.append(f"a.year IN ({placeholders})")
            parameters.extend(decision.years)
        if decision.facilities:
            placeholders = ", ".join("?" for _ in decision.facilities)
            clauses.append(f"f.facility_name IN ({placeholders})")
            parameters.extend(decision.facilities)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), tuple(parameters)

    @staticmethod
    def _rollup(metric, column: str) -> str:
        if metric.fleet_aggregation == "sum":
            return f"SUM(a.{column})"
        count_column = COUNT_COLUMNS[metric.table]
        return (
            f"SUM(a.{column} * a.{count_column}) / "
            f"NULLIF(SUM(a.{count_column}), 0)"
        )

    def build(self, decision: RouteDecision) -> TemplateQuery:
        if not decision.metric_key or decision.metric_key not in self.metrics:
            raise ValueError("A supported metric is required for a query template")
        metric = self.metrics[decision.metric_key]
        column = AGGREGATE_COLUMNS[metric.key]
        where, parameters = self._where(decision)
        route = decision.category

        if route == "RANKING":
            value = f"a.{column}" if len(decision.years) == 1 else self._rollup(metric, column)
            group = "" if len(decision.years) == 1 else " GROUP BY f.facility_name"
            limit = " LIMIT 1" if decision.top_one else ""
            sql = (
                f"SELECT f.facility_name, {value} AS metric_value "
                "FROM agg_facility_yearly AS a "
                "JOIN facilities AS f ON f.facility_id = a.facility_id"
                f"{where}{group} ORDER BY metric_value {decision.ranking_direction}{limit}"
            )
        elif route in {"COMPARISON", "TREND"}:
            if decision.facilities or decision.group_by_facility:
                sql = (
                    f"SELECT f.facility_name, a.year, a.{column} AS metric_value "
                    "FROM agg_facility_yearly AS a "
                    "JOIN facilities AS f ON f.facility_id = a.facility_id"
                    f"{where} ORDER BY f.facility_name, a.year"
                )
            else:
                sql = (
                    f"SELECT a.year, {self._rollup(metric, column)} AS metric_value "
                    "FROM agg_facility_yearly AS a "
                    "JOIN facilities AS f ON f.facility_id = a.facility_id"
                    f"{where} GROUP BY a.year ORDER BY a.year"
                )
        else:
            if decision.facilities and len(decision.years) == 1:
                sql = (
                    f"SELECT f.facility_name, a.year, a.{column} AS metric_value "
                    "FROM agg_facility_yearly AS a "
                    "JOIN facilities AS f ON f.facility_id = a.facility_id"
                    f"{where} ORDER BY f.facility_name"
                )
            elif len(decision.years) == 1:
                sql = (
                    f"SELECT a.year, {self._rollup(metric, column)} AS metric_value "
                    "FROM agg_facility_yearly AS a "
                    "JOIN facilities AS f ON f.facility_id = a.facility_id"
                    f"{where} GROUP BY a.year"
                )
            else:
                sql = (
                    f"SELECT {self._rollup(metric, column)} AS metric_value "
                    "FROM agg_facility_yearly AS a "
                    "JOIN facilities AS f ON f.facility_id = a.facility_id"
                    f"{where}"
                )
        return TemplateQuery(sql, parameters, decision, metric.display_name, metric.unit)

    @staticmethod
    def answer(query: TemplateQuery, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "No matching records were found for that analytical question."
        unit = "" if query.unit == "ratio" else f" {query.unit}"
        if len(frame) == 1:
            row = frame.iloc[0]
            scope = row.get("facility_name", "All Facilities")
            year = f" in {int(row['year'])}" if "year" in row else ""
            return (
                f"**{scope} — {query.display_name}:** "
                f"{float(row['metric_value']):,.4f}{unit}{year}."
            )
        if query.route.category == "RANKING":
            leader = frame.iloc[0]
            return (
                f"The leading result is **{leader['facility_name']}** at "
                f"**{float(leader['metric_value']):,.4f}{unit}**. "
                "The complete ranking is shown below."
            )
        return (
            f"The {query.display_name} comparison returned {len(frame)} grounded rows. "
            "The table and chart below contain the exact values."
        )
