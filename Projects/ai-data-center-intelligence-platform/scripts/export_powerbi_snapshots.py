"""Export compact, governed snapshots for Power BI advanced pages.

The report imports these reviewed aggregates instead of querying the volatile
real-time event store or recomputing analytical assumptions inside DAX.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.sustainability.engine import CostCarbonEngine


PROCESSED = ROOT / "data" / "processed"
CANONICAL_DB = ROOT / "database" / "datacenter.db"
REALTIME_DB = ROOT / "database" / "realtime.db"


def _sustainability_engine() -> CostCarbonEngine:
    return CostCarbonEngine(
        CANONICAL_DB,
        ROOT / "data" / "assumptions" / "energy_prices.csv",
        ROOT / "data" / "assumptions" / "carbon_intensity.csv",
        ROOT / "analytics" / "efficiency_opportunity_weights.yaml",
    )


def _round_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.select_dtypes(include=["number"]).columns
    frame[numeric] = frame[numeric].round(4)
    return frame


def export_cost_carbon() -> pd.DataFrame:
    """Monthly facility snapshot using the governed cost/carbon engine."""
    engine = _sustainability_engine()
    daily = engine.daily_model()
    daily["snapshot_date"] = daily["timestamp"].dt.to_period("M").dt.to_timestamp()
    additive = [
        "modeled_energy_kwh",
        "modeled_it_energy_kwh",
        "modeled_cooling_energy_kwh",
        "modeled_energy_cost_usd",
        "modeled_it_cost_usd",
        "modeled_cooling_cost_usd",
        "modeled_carbon_tonnes",
        "modeled_it_carbon_tonnes",
        "modeled_cooling_carbon_tonnes",
    ]
    monthly = daily.groupby(
        ["snapshot_date", "facility_id", "facility_name"], as_index=False
    ).agg(
        **{name: (name, "sum") for name in additive},
        average_pue=("pue", "mean"),
        price_per_kwh=("price_per_kwh", "mean"),
        grams_co2e_per_kwh=("grams_co2e_per_kwh", "mean"),
        observation_days=("timestamp", "nunique"),
        currency=("currency", "first"),
        pricing_basis=("pricing_basis", "first"),
        price_source=("price_source", "first"),
        carbon_methodology=("methodology", "first"),
        carbon_source=("carbon_source", "first"),
    )
    current = engine.summarize("2025-01-01", "2025-12-31").frame[
        ["facility_id", "efficiency_opportunity_score"]
    ]
    monthly = monthly.merge(current, on="facility_id", how="left", validate="many_to_one")
    monthly["year"] = monthly["snapshot_date"].dt.year
    monthly["month_label"] = monthly["snapshot_date"].dt.strftime("%b %Y")
    monthly["assumptions_are_synthetic"] = True
    monthly["snapshot_version"] = "cost-carbon-v1"
    monthly["source_period"] = "2015-01-01 to 2025-12-31"
    ordered = [
        "snapshot_date", "year", "month_label", "facility_id", "facility_name",
        "observation_days", *additive, "average_pue", "price_per_kwh",
        "grams_co2e_per_kwh", "efficiency_opportunity_score", "currency",
        "pricing_basis", "price_source", "carbon_methodology", "carbon_source",
        "assumptions_are_synthetic", "snapshot_version", "source_period",
    ]
    return _round_numeric(monthly[ordered].sort_values(
        ["snapshot_date", "facility_id"]
    ).reset_index(drop=True))


def export_incident_impact(cost_carbon: pd.DataFrame) -> pd.DataFrame:
    """Incident-level descriptive before/after evidence; no causal claim."""
    with sqlite3.connect(CANONICAL_DB) as connection:
        incidents = pd.read_sql_query(
            """SELECT i.incident_id, date(i.start_time) AS incident_date,
                i.facility_id, f.facility_name, i.server_id, i.severity,
                i.root_cause, i.status, i.downtime_minutes
                FROM uptime_incidents AS i
                JOIN facilities AS f USING (facility_id)
                ORDER BY i.start_time, i.incident_id""",
            connection,
        )
        daily = pd.read_sql_query(
            """SELECT p.facility_id, date(p.timestamp) AS date, p.pue,
                n.latency_ms, n.packet_loss_pct, n.network_availability_pct
                FROM power_metrics AS p
                JOIN network_metrics AS n
                  ON n.facility_id=p.facility_id AND date(n.timestamp)=date(p.timestamp)
                ORDER BY p.facility_id, p.timestamp""",
            connection,
        )
    incidents["incident_date"] = pd.to_datetime(incidents["incident_date"])
    daily["date"] = pd.to_datetime(daily["date"])
    metrics = ("pue", "latency_ms", "packet_loss_pct", "network_availability_pct")
    # Precompute seven-day windows once at the daily facility grain. This keeps
    # snapshot generation fast while retaining the same descriptive design used
    # by the impact engine.
    daily = daily.sort_values(["facility_id", "date"]).reset_index(drop=True)
    for metric in metrics:
        daily[f"before_{metric}"] = daily.groupby("facility_id")[metric].transform(
            lambda values: values.shift(1).rolling(7, min_periods=1).mean()
        )
        daily[f"after_{metric}"] = daily.groupby("facility_id")[metric].transform(
            lambda values: values.iloc[::-1].shift(1).rolling(7, min_periods=1).mean().iloc[::-1]
        )
        daily = daily.rename(columns={metric: f"during_{metric}"})
    incidents = incidents.merge(
        daily,
        left_on=["facility_id", "incident_date"],
        right_on=["facility_id", "date"],
        how="left",
        validate="many_to_one",
    ).drop(columns="date")
    cost_lookup = cost_carbon.set_index(["facility_id", "snapshot_date"])[
        "modeled_energy_cost_usd"
    ].to_dict()
    records: list[dict[str, object]] = []
    for row in incidents.itertuples(index=False):
        anchor = row.incident_date
        record = row._asdict()
        for metric in metrics:
            before = float(record[f"before_{metric}"])
            after = float(record[f"after_{metric}"])
            record[f"change_{metric}_pct"] = (
                100.0 * (after - before) / before if before and np.isfinite(before) else np.nan
            )
        month = anchor.to_period("M").to_timestamp()
        monthly_cost = float(cost_lookup.get((row.facility_id, month), 0.0))
        observation_days = int(anchor.days_in_month)
        record["modeled_downtime_cost_exposure_usd"] = (
            monthly_cost / observation_days * float(row.downtime_minutes) / 1440.0
        )
        record["comparison_window_days"] = 7
        record["claim_level"] = "descriptive_before_after"
        record["is_synthetic"] = True
        record["snapshot_version"] = "incident-impact-v1"
        records.append(record)
    return _round_numeric(pd.DataFrame.from_records(records))


def export_live_operations() -> pd.DataFrame:
    """Latest facility health only; raw real-time events never enter Power BI."""
    columns = [
        "simulation_session_id", "scenario_name", "session_status",
        "snapshot_timestamp", "facility_id", "facility_name", "health_score",
        "energy_efficiency_score", "reliability_score", "network_health_score",
        "infrastructure_score", "alert_score", "anomaly_score",
        "active_alert_count", "active_anomaly_count", "data_completeness_pct",
        "method_version", "is_synthetic", "snapshot_version",
    ]
    if not REALTIME_DB.exists():
        return pd.DataFrame(columns=columns)
    with sqlite3.connect(REALTIME_DB) as realtime, sqlite3.connect(CANONICAL_DB) as canonical:
        latest = realtime.execute(
            """SELECT simulation_session_id FROM simulation_sessions
            ORDER BY updated_at DESC, simulation_session_id DESC LIMIT 1"""
        ).fetchone()
        if latest is None:
            return pd.DataFrame(columns=columns)
        frame = pd.read_sql_query(
            """SELECT h.simulation_session_id, s.scenario_name,
                s.status AS session_status, h.score_timestamp AS snapshot_timestamp,
                h.facility_id, h.health_score, h.energy_efficiency_score,
                h.reliability_score, h.network_health_score,
                h.infrastructure_score, h.alert_score, h.anomaly_score,
                h.active_alert_count, h.active_anomaly_count,
                h.data_completeness_pct, h.method_version
                FROM realtime_facility_health AS h
                JOIN simulation_sessions AS s USING (simulation_session_id)
                WHERE h.simulation_session_id=?
                ORDER BY h.facility_id""",
            realtime,
            params=[latest[0]],
        )
        facilities = pd.read_sql_query(
            "SELECT facility_id, facility_name FROM facilities", canonical
        )
    frame = frame.merge(facilities, on="facility_id", how="left", validate="one_to_one")
    frame["is_synthetic"] = True
    frame["snapshot_version"] = "live-operations-v1"
    return _round_numeric(frame[columns])


def export_all() -> dict[str, int]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    cost_carbon = export_cost_carbon()
    incident_impact = export_incident_impact(cost_carbon)
    live_operations = export_live_operations()
    outputs = {
        "powerbi_cost_carbon_snapshot.csv": cost_carbon,
        "powerbi_incident_impact_snapshot.csv": incident_impact,
        "powerbi_live_operations_snapshot.csv": live_operations,
    }
    for filename, frame in outputs.items():
        frame.to_csv(PROCESSED / filename, index=False, lineterminator="\n")
    return {filename: len(frame) for filename, frame in outputs.items()}


if __name__ == "__main__":
    for name, count in export_all().items():
        print(f"{name}: {count} rows")
