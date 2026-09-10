from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.database import connect_read_only


@dataclass(frozen=True)
class MetricSpec:
    key: str
    display_name: str
    unit: str
    aliases: tuple[str, ...]
    table: str
    date_column: str
    value_expression: str
    annual_aggregation: str
    fleet_aggregation: str
    joins: str
    lower_bound: float | None = None
    upper_bound: float | None = None


METRICS = (
    MetricSpec("average_pue", "PUE", "ratio", (r"\bpue\b", r"power usage effectiveness"), "power_metrics", "p.timestamp", "p.pue", "AVG", "mean", "JOIN facilities f ON f.facility_id=p.facility_id", 1, 2),
    MetricSpec("power_draw_kw", "Average Power Draw", "kW", (r"power draw", r"facility power", r"\bpower\b"), "power_metrics", "p.timestamp", "p.power_draw_kw", "AVG", "mean", "JOIN facilities f ON f.facility_id=p.facility_id", 0),
    MetricSpec("it_load_kw", "Average IT Load", "kW", (r"it load", r"it power", r"compute power"), "power_metrics", "p.timestamp", "p.it_load_kw", "AVG", "mean", "JOIN facilities f ON f.facility_id=p.facility_id", 0),
    MetricSpec("cooling_power_kw", "Average Cooling Power", "kW", (r"cooling power", r"cooling demand", r"\bcooling\b"), "power_metrics", "p.timestamp", "p.cooling_power_kw", "AVG", "mean", "JOIN facilities f ON f.facility_id=p.facility_id", 0),
    MetricSpec("cooling_cost", "Annual Cooling Cost", "currency-equivalent", (r"cooling cost", r"cooling expense", r"cooling price", r"price of cooling", r"cost of cooling"), "power_metrics", "p.timestamp", "p.cooling_cost", "SUM", "sum", "JOIN facilities f ON f.facility_id=p.facility_id", 0),
    MetricSpec("cpu_utilization_pct", "CPU Utilization", "%", (r"cpu utilization", r"cpu usage", r"\bcpu\b"), "server_metrics", "sm.timestamp", "sm.cpu_utilization_pct", "AVG", "mean", "JOIN servers s ON s.server_id=sm.server_id JOIN facilities f ON f.facility_id=s.facility_id", 0, 100),
    MetricSpec("memory_utilization_pct", "Memory Utilization", "%", (r"memory utilization", r"memory usage", r"\bmemory\b"), "server_metrics", "sm.timestamp", "sm.memory_utilization_pct", "AVG", "mean", "JOIN servers s ON s.server_id=sm.server_id JOIN facilities f ON f.facility_id=s.facility_id", 0, 100),
    MetricSpec("disk_utilization_pct", "Disk Utilization", "%", (r"disk utilization", r"disk usage", r"storage utilization", r"\bdisk\b"), "server_metrics", "sm.timestamp", "sm.disk_utilization_pct", "AVG", "mean", "JOIN servers s ON s.server_id=sm.server_id JOIN facilities f ON f.facility_id=s.facility_id", 0, 100),
    MetricSpec("server_network_utilization_pct", "Server Network Utilization", "%", (r"server network utilization", r"network utilization per server"), "server_metrics", "sm.timestamp", "sm.network_utilization_pct", "AVG", "mean", "JOIN servers s ON s.server_id=sm.server_id JOIN facilities f ON f.facility_id=s.facility_id", 0, 100),
    MetricSpec("bandwidth_utilization_pct", "Bandwidth Utilization", "%", (r"bandwidth utilization", r"bandwidth usage", r"\bbandwidth\b"), "network_metrics", "n.timestamp", "n.bandwidth_utilization_pct", "AVG", "mean", "JOIN facilities f ON f.facility_id=n.facility_id", 0, 100),
    MetricSpec("latency_ms", "Network Latency", "ms", (r"network latency", r"\blatency\b"), "network_metrics", "n.timestamp", "n.latency_ms", "AVG", "mean", "JOIN facilities f ON f.facility_id=n.facility_id", 0),
    MetricSpec("packet_loss_pct", "Packet Loss", "%", (r"packet loss",), "network_metrics", "n.timestamp", "n.packet_loss_pct", "AVG", "mean", "JOIN facilities f ON f.facility_id=n.facility_id", 0, 100),
    MetricSpec("throughput_mbps", "Network Throughput", "Mbps", (r"network throughput", r"\bthroughput\b"), "network_metrics", "n.timestamp", "n.throughput_mbps", "AVG", "mean", "JOIN facilities f ON f.facility_id=n.facility_id", 0),
    MetricSpec("network_availability_pct", "Network Availability", "%", (r"network availability",), "network_metrics", "n.timestamp", "n.network_availability_pct", "AVG", "mean", "JOIN facilities f ON f.facility_id=n.facility_id", 0, 100),
    MetricSpec("downtime_minutes", "Annual Downtime", "minutes", (r"downtime", r"outage minutes"), "uptime_incidents", "i.start_time", "i.downtime_minutes", "SUM", "sum", "JOIN facilities f ON f.facility_id=i.facility_id", 0),
    MetricSpec("incident_count", "Annual Incident Count", "incidents", (r"incident count", r"number of incidents", r"how many incidents", r"\bincidents?\b"), "uptime_incidents", "i.start_time", "i.incident_id", "COUNT", "sum", "JOIN facilities f ON f.facility_id=i.facility_id", 0),
)


AGGREGATE_COLUMNS = {
    "average_pue": "average_pue",
    "power_draw_kw": "average_power_draw_kw",
    "it_load_kw": "average_it_load_kw",
    "cooling_power_kw": "average_cooling_power_kw",
    "cooling_cost": "total_cooling_cost",
    "cpu_utilization_pct": "average_cpu_utilization_pct",
    "memory_utilization_pct": "average_memory_utilization_pct",
    "disk_utilization_pct": "average_disk_utilization_pct",
    "server_network_utilization_pct": "average_server_network_utilization_pct",
    "bandwidth_utilization_pct": "average_bandwidth_utilization_pct",
    "latency_ms": "average_latency_ms",
    "packet_loss_pct": "average_packet_loss_pct",
    "throughput_mbps": "average_throughput_mbps",
    "network_availability_pct": "average_network_availability_pct",
    "downtime_minutes": "total_downtime_minutes",
    "incident_count": "incident_count",
}


@dataclass
class ForecastOutput:
    frame: pd.DataFrame
    metric: MetricSpec
    training_start_year: int
    training_end_year: int
    target_year: int
    source_sql: str
    execution_ms: float


def detect_metric(question: str) -> MetricSpec | None:
    lower = question.lower()
    matches = [
        (len(pattern), spec) for spec in METRICS for pattern in spec.aliases
        if re.search(pattern, lower)
    ]
    if re.search(r"\b(price|cost|expense|tariff)\b", lower):
        monetary = [item for item in matches if item[1].unit == "currency-equivalent"]
        if monetary:
            return max(monetary, key=lambda item: item[0])[1]
        if not re.search(r"\b(?:price|cost|expense|tariff)\s+(?:of|for)\s+\w+", lower):
            return next(spec for spec in METRICS if spec.key == "cooling_cost")
        return None
    return max(matches, key=lambda item: item[0])[1] if matches else None


def detect_metrics(question: str) -> list[MetricSpec]:
    lower = question.lower()
    matched = []
    for spec in METRICS:
        if any(re.search(pattern, lower) for pattern in spec.aliases):
            matched.append(spec)
    keys = {spec.key for spec in matched}
    if "cooling_cost" in keys and "cooling_power_kw" in keys and not re.search(r"cooling (power|demand)", lower):
        matched = [spec for spec in matched if spec.key != "cooling_power_kw"]
    if "power_draw_kw" in {spec.key for spec in matched} and not re.search(r"power draw|facility power", lower):
        if any(spec.key in {"cooling_power_kw", "it_load_kw"} for spec in matched):
            matched = [spec for spec in matched if spec.key != "power_draw_kw"]
    return matched


def supported_metric_names() -> list[str]:
    return [spec.display_name for spec in METRICS]


def has_forecast_intent(question: str) -> bool:
    return bool(re.search(r"\b(forecast|predict|prediction|project|projection|future|will|estimate|expected)\b", question.lower()))


def asks_trend_direction(question: str) -> bool:
    return bool(re.search(
        r"\b(increase|increse|decrease|decrese|rise|fall|grow|decline|up|down|trend)\b",
        question.lower(),
    ))


def contextualize_question(
    question: str,
    previous_metric: MetricSpec | None,
    previous_year: int | None = None,
    previous_facilities: list[str] | None = None,
    latest_complete_year: int = 2025,
) -> str:
    if previous_metric is None:
        return question
    stripped = question.strip()
    lower = stripped.lower()
    previous_facilities = previous_facilities or []
    mentioned_facility = bool(re.search(
        r"\b(frankfurt|dublin|ashburn|portland|singapore|sydney)\b", lower
    ))
    facility_text = f" for {', '.join(previous_facilities)}" if previous_facilities else ""
    if re.fullmatch(r"20\d{2}\??", stripped):
        year = int(re.search(r"20\d{2}", stripped).group(0))
        action = "Forecast" if year > latest_complete_year else "Show"
        return f"{action} {previous_metric.display_name}{facility_text} in {year}"

    follow_up = bool(re.search(
        r"^(and\b|also\b|what about\b|how about\b|same\b)|"
        r"\b(it|that|those|same|why|increase|increse|decrease|decrese|rise|fall|up|down)\b",
        lower,
    ))
    if not follow_up:
        return question

    additions = []
    if detect_metric(stripped) is None:
        additions.append(previous_metric.display_name)
    if previous_facilities and not mentioned_facility:
        additions.append(", ".join(previous_facilities))
    has_year = bool(re.search(r"\b20\d{2}\b", lower))
    if previous_year and not has_year and not asks_trend_direction(stripped):
        additions.append(str(previous_year))
    if additions:
        return f"{stripped.rstrip('?')} for {' in '.join(additions)}?"
    return question


def resolve_target_year(question: str, latest_complete_year: int) -> int | None:
    lower = question.lower()
    explicit = [int(year) for year in re.findall(r"\b(20\d{2})\b", lower) if int(year) > latest_complete_year]
    if explicit:
        return max(explicit)
    if re.search(r"\bnext year\b", lower):
        return latest_complete_year + 1
    relative = re.search(r"\b(?:in|after)\s+(\d{1,2})\s+years?\b|\b(\d{1,2})\s+years?\s+from now\b", lower)
    if relative:
        years_ahead = int(relative.group(1) or relative.group(2))
        return latest_complete_year + years_ahead
    word_values = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    word_relative = re.search(
        r"\b(?:in|after)\s+(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?\b|"
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?\s+from now\b",
        lower,
    )
    if word_relative:
        return latest_complete_year + word_values[word_relative.group(1) or word_relative.group(2)]
    return None


def _fit_linear(years: np.ndarray, values: np.ndarray, target_year: int) -> dict[str, float]:
    if len(years) < 4:
        raise ValueError("At least four complete annual observations are required")
    centered = years - years.mean()
    design = np.column_stack([np.ones(len(years)), centered])
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    fitted_values = design @ coefficients
    residuals = values - fitted_values
    residual_std = math.sqrt(float(np.sum(residuals**2)) / (len(years) - 2))
    target_offset = float(target_year - years.mean())
    prediction = float(coefficients[0] + coefficients[1] * target_offset)
    leverage = (1 / len(years)) + (target_offset**2 / float(np.sum(centered**2)))
    interval = 1.96 * residual_std * math.sqrt(1 + leverage)
    total_variance = float(np.sum((values - values.mean()) ** 2))
    r_squared = 1 - float(np.sum(residuals**2)) / total_variance if total_variance else 1.0
    return {
        "prediction": prediction, "lower": prediction - interval, "upper": prediction + interval,
        "trend_per_year": float(coefficients[1]), "r_squared": r_squared,
    }


def _rolling_backtest_mae(years: np.ndarray, values: np.ndarray) -> float:
    errors = [
        abs(_fit_linear(years[:index], values[:index], int(years[index]))["prediction"] - float(values[index]))
        for index in range(4, len(years))
    ]
    return float(np.mean(errors)) if errors else float("nan")


def _bound(value: float, spec: MetricSpec) -> float:
    if spec.lower_bound is not None:
        value = max(spec.lower_bound, value)
    if spec.upper_bound is not None:
        value = min(spec.upper_bound, value)
    return value


class MetricForecaster:
    """Refit governed annual metric trends from the current database for every request."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = database_path

    def latest_complete_year(self) -> int:
        with connect_read_only(self.database_path) as connection:
            latest = connection.execute("SELECT MAX(timestamp) FROM power_metrics").fetchone()[0]
        if not latest:
            raise ValueError("Cannot determine the dataset date boundary")
        year = int(str(latest)[:4])
        return year if str(latest)[5:10] == "12-31" else year - 1

    @staticmethod
    def source_sql(
        spec: MetricSpec, complete_year: int, use_aggregate: bool = False
    ) -> str:
        if use_aggregate:
            aggregate_column = AGGREGATE_COLUMNS[spec.key]
            return f"""SELECT
    f.facility_name,
    a.year,
    a.{aggregate_column} AS metric_value
FROM agg_facility_yearly AS a
JOIN facilities AS f ON f.facility_id = a.facility_id
WHERE a.year <= {complete_year}
ORDER BY f.facility_name, a.year"""
        alias = {"power_metrics": "p", "server_metrics": "sm", "network_metrics": "n", "uptime_incidents": "i"}[spec.table]
        return f"""SELECT
    f.facility_name,
    CAST(substr({spec.date_column}, 1, 4) AS INTEGER) AS year,
    {spec.annual_aggregation}({spec.value_expression}) AS metric_value
FROM {spec.table} AS {alias}
{spec.joins}
WHERE CAST(substr({spec.date_column}, 1, 4) AS INTEGER) <= {complete_year}
GROUP BY f.facility_name, CAST(substr({spec.date_column}, 1, 4) AS INTEGER)
ORDER BY f.facility_name, year"""

    def load_history(self, spec: MetricSpec) -> tuple[pd.DataFrame, str]:
        complete_year = self.latest_complete_year()
        with connect_read_only(self.database_path) as connection:
            use_aggregate = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'agg_facility_yearly'"
            ).fetchone() is not None
            sql = self.source_sql(spec, complete_year, use_aggregate=use_aggregate)
            frame = pd.read_sql_query(sql, connection)
        if frame.empty:
            raise ValueError(f"No history is available for {spec.display_name}")
        return frame, sql

    def forecast(self, spec: MetricSpec, target_year: int, facilities: list[str] | None = None) -> ForecastOutput:
        started = time.perf_counter()
        history, sql = self.load_history(spec)
        training_start = int(history["year"].min())
        training_end = int(history["year"].max())
        if target_year <= training_end:
            raise ValueError(f"Forecast year must be later than the latest complete year ({training_end})")
        requested = set(facilities or [])
        if requested:
            history = history[history["facility_name"].isin(requested)]
            missing = requested - set(history["facility_name"])
            if missing:
                raise ValueError(f"Unknown facility name(s): {', '.join(sorted(missing))}")

        series: list[tuple[str, pd.DataFrame]] = []
        if not requested:
            operation = "sum" if spec.fleet_aggregation == "sum" else "mean"
            overall = history.groupby("year", as_index=False).agg(metric_value=("metric_value", operation))
            series.append(("All Facilities", overall))
        series.extend((name, group[["year", "metric_value"]]) for name, group in history.groupby("facility_name"))

        records = []
        for facility_name, group in series:
            group = group.sort_values("year")
            years = group["year"].to_numpy(dtype=float)
            values = group["metric_value"].to_numpy(dtype=float)
            fitted = _fit_linear(years, values, target_year)
            records.append({
                "facility_name": facility_name,
                "metric": spec.display_name,
                "forecast_year": target_year,
                "predicted_value": round(_bound(fitted["prediction"], spec), 4),
                "lower_95": round(_bound(fitted["lower"], spec), 4),
                "upper_95": round(_bound(fitted["upper"], spec), 4),
                "unit": spec.unit,
                "trend_per_year": round(fitted["trend_per_year"], 5),
                "r_squared": round(fitted["r_squared"], 4),
                "backtest_mae": round(_rolling_backtest_mae(years, values), 4),
                "training_start_year": int(years.min()),
                "training_end_year": int(years.max()),
                "historical_years": len(years),
            })
        return ForecastOutput(
            pd.DataFrame(records), spec, training_start, training_end, target_year, sql,
            (time.perf_counter() - started) * 1000,
        )

    def historical(self, spec: MetricSpec, years: list[int], facilities: list[str] | None = None) -> tuple[pd.DataFrame, str]:
        history, sql = self.load_history(spec)
        requested = sorted(set(years))
        history = history[history["year"].isin(requested)]
        if history.empty:
            raise ValueError(f"No {spec.display_name} history exists for the requested year(s)")
        if facilities:
            history = history[history["facility_name"].isin(set(facilities))]
            if history.empty:
                raise ValueError("No matching facility history exists")
            scoped = history.rename(columns={"metric_value": "value"})
        else:
            operation = "sum" if spec.fleet_aggregation == "sum" else "mean"
            scoped = history.groupby("year", as_index=False).agg(value=("metric_value", operation))
            scoped.insert(0, "facility_name", "All Facilities")
        scoped.insert(1, "metric", spec.display_name)
        scoped["unit"] = spec.unit
        return scoped[["facility_name", "metric", "year", "value", "unit"]].sort_values(["facility_name", "year"]), sql
