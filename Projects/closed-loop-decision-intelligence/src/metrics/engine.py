"""Reaggregate numerators and denominators; never average cohort ratios."""
import numpy as np
import pandas as pd
from pydantic import BaseModel
from sqlalchemy import text

from src.common.config import ROOT, read_config
from src.common.store import identity

DIMENSIONS = ["country", "device", "channel", "product_category", "customer_segment"]
GRAINS = {"hourly": "h", "daily": "D", "weekly": "W-SUN", "monthly": "M"}


class Metric(BaseModel):
    metric_id: str
    name: str
    description: str
    owner: str
    source: str = "analytics.cohort_mart"
    aggregation: str
    numerator: str
    denominator: str | None = None
    complement: bool = False
    direction: str
    warning_threshold: float = .2
    critical_threshold: float = .4
    comparison_method: str = "trailing_same_weekday"
    monitoring_frequency: str = "daily"
    grain: str = "daily"
    dimensions: list[str] = DIMENSIONS
    enabled: bool = True


def registry() -> list[Metric]:
    return [Metric(**row) for row in read_config("metrics")["metrics"] if row.get("enabled", True)]


def load_mart(engine, include_customers=False) -> pd.DataFrame:
    """Production uses the tested dbt mart; SQLite uses identical portable SQL."""
    with engine.connect() as connection:
        if engine.dialect.name == "postgresql":
            query = "SELECT * FROM analytics.cohort_mart"
        else:
            query = (ROOT / "sql/analytics/cohort_mart.sql").read_text().replace("raw.", "")
        frame = pd.read_sql(text(query), connection)
        if include_customers:
            from sqlalchemy import select

            from src.common.models import orders
            activity = pd.read_sql(select(orders.c.cohort_id, orders.c.customer_id).where(orders.c.status == "PAID"), connection)
            customer_sets = activity.groupby("cohort_id").customer_id.agg(frozenset)
            frame["_customer_ids"] = frame.id.map(customer_sets).apply(lambda x: x if isinstance(x, frozenset) else frozenset())
    frame["timestamp"] = pd.to_datetime(frame.timestamp)
    frame["country_device"] = frame.country + " / " + frame.device
    return frame


def aggregate(frame: pd.DataFrame, metric: Metric, grain="daily", dimension="all") -> pd.DataFrame:
    if grain not in GRAINS:
        raise ValueError(f"Unsupported grain: {grain}")
    if dimension not in ["all", "country_device", *DIMENSIONS]:
        raise ValueError(f"Unsupported dimension: {dimension}")
    data = frame.copy()
    if grain in ("monthly", "weekly"):
        data["timestamp"] = data.timestamp.dt.to_period(GRAINS[grain]).dt.start_time
    else:
        data["timestamp"] = data.timestamp.dt.floor(GRAINS[grain])
    data["dimension_value"] = "all" if dimension == "all" else data[dimension]
    keys = ["timestamp", "dimension_value"]
    columns = list(dict.fromkeys([metric.numerator] + ([metric.denominator] if metric.denominator else [])))
    grouped = data.groupby(keys, observed=True)[columns].sum(min_count=1)
    if metric.aggregation == "distinct_count":
        value = data.groupby(keys, observed=True)._customer_ids.agg(lambda sets: len(set().union(*sets)))
    else:
        value = grouped[metric.numerator]
    if metric.denominator:
        value = value / grouped[metric.denominator].replace(0, np.nan)
    if metric.complement:
        value = 1-value
    result = value.rename("actual_value").reset_index()
    result["metric_id"], result["dimension_name"], result["grain"] = metric.metric_id, dimension, grain
    return result


def observations(frame: pd.DataFrame, dimensions=None, grain="daily") -> pd.DataFrame:
    """Baselines use strictly prior observations, matched on weekday for daily grain."""
    parts = []
    for metric in registry():
        for dimension in dimensions or ["all", "country_device", "channel", "product_category", "country"]:
            result = aggregate(frame, metric, grain, dimension).sort_values("timestamp")
            result["weekday"] = result.timestamp.dt.weekday if grain == "daily" else 0
            result["baseline_value"] = result.groupby(["dimension_value", "weekday"]).actual_value.transform(
                lambda x: x.shift(1).rolling(8, min_periods=4).median())
            result["expected_value"] = result.baseline_value
            result["deviation_absolute"] = result.actual_value-result.baseline_value
            result["deviation_percent"] = result.deviation_absolute/result.baseline_value.replace(0, np.nan)
            result["id"] = [identity(metric.metric_id, t, dimension, v, grain)
                            for t, v in zip(result.timestamp, result.dimension_value)]
            parts.append(result.drop(columns="weekday"))
    return pd.concat(parts, ignore_index=True)
