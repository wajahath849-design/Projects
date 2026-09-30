"""Persist investigations, forecasts and measured outcomes."""

import pandas as pd
from sqlalchemy import delete, select, update

from src.common import models as m
from src.common.store import identity, now, one, records, upsert
from src.decision_memory.service import learn
from src.forecasting.engine import forecast
from src.impact.statistics import measure
from src.investigation.engine import contributions, investigate
from src.metrics.engine import aggregate, load_mart, registry


def investigate_incident(engine, anomaly_id: str, frame=None) -> dict:
    frame = load_mart(engine) if frame is None else frame
    with engine.begin() as connection:
        existing = records(connection, m.hypotheses, m.hypotheses.c.id == anomaly_id)
        complete = records(connection, m.evidence, (m.evidence.c.incident_id == anomaly_id)
                           & (m.evidence.c.dimension == "payment_provider"))
        if existing and complete:
            return existing[0]
        anomaly = one(connection, m.anomalies, anomaly_id)
        one(connection, m.incidents, anomaly_id)
        result = investigate(frame, anomaly, records(connection, m.deployments), records(connection, m.operational_incidents))
        day = pd.Timestamp(anomaly["timestamp"]).normalize()
        transactions = pd.read_sql(select(m.orders.c.timestamp, m.orders.c.amount.label("revenue"),
            m.orders.c.is_new, m.payments.c.provider.label("payment_provider"))
            .join(m.payments, m.payments.c.order_id == m.orders.c.id)
            .where((m.orders.c.status == "PAID") & (m.orders.c.timestamp >= day-pd.Timedelta(days=56))
                   & (m.orders.c.timestamp < day+pd.Timedelta(days=1))), connection)
        transactions["timestamp"] = pd.to_datetime(transactions.timestamp)
        transactions["hour"] = transactions.timestamp.dt.hour.astype(str)
        transactions["new_vs_returning"] = transactions.is_new.map({1: "New", 0: "Returning"})
        extra = contributions(transactions, day, dimensions=["payment_provider", "hour", "new_vs_returning"])
        for row in extra:
            row.update(id=identity(anomaly_id, row["dimension"], row["segment"]), incident_id=anomaly_id,
                       evidence_type="CONTRIBUTION")
        result["evidence"].extend(extra)
        upsert(connection, m.evidence, result["evidence"])
        row = dict(id=anomaly_id, incident_id=anomaly_id, driver=result["driver"], description=result["description"],
                   confidence=result["confidence"], signals=result["signals"])
        upsert(connection, m.hypotheses, [row])
        connection.execute(update(m.incidents).where(m.incidents.c.id == anomaly_id).values(
            driver=result["driver"], status="INVESTIGATED"))
        return row


def forecast_incident(engine, incident_id: str, frame=None, force=False) -> dict:
    frame = load_mart(engine) if frame is None else frame
    with engine.begin() as connection:
        existing = records(connection, m.forecasts, m.forecasts.c.incident_id == incident_id)
        if existing and not force:
            return {"forecasts": len(existing)}
        if force:
            connection.execute(delete(m.forecasts).where(m.forecasts.c.incident_id == incident_id))
        incident = one(connection, m.incidents, incident_id)
        day = pd.Timestamp(incident["detected_at"]).normalize()
        rows = []
        metrics = {r.metric_id: r for r in registry()}
        for name in ["revenue", "orders", "conversion", "churn", "cac", "support_volume"]:
            series = aggregate(frame[frame.timestamp < day], metrics[name])
            if name == "conversion":
                traffic = frame[frame.timestamp < day].groupby(frame.timestamp.dt.normalize())[["sessions", "server_sessions"]].sum()
                invalid_days = traffic.index[traffic.sessions / traffic.server_sessions.replace(0, float("nan")) < .5]
                series.loc[series.timestamp.isin(invalid_days), "actual_value"] = float("nan")
            if len(series.dropna(subset=["actual_value"])) < 28:
                continue
            prediction = forecast(series.actual_value.tail(84), 30, bounded=name in ("conversion", "churn"))
            actual_frame = aggregate(frame[frame.timestamp.dt.normalize() == day], metrics[name])
            actual = float(actual_frame.actual_value.iloc[0]) if len(actual_frame) else 0
            for step, (center, lower, upper) in enumerate(zip(prediction["expected"], prediction["lower"], prediction["upper"]), 1):
                rows.append(dict(id=identity(incident_id, name, step), incident_id=incident_id, metric=name,
                    timestamp=(day+pd.Timedelta(days=step)).to_pydatetime(), horizon=step,
                    expected=center, lower=lower, upper=upper,
                    exposure=max(center-actual, 0) if name == "revenue" else 0., method=prediction["method"]))
            upsert(connection, m.model_runs, [dict(id=identity(incident_id, name, "quality_screened_v2"), model_name=prediction["method"],
                run_id=incident_id, parameters={"metric": name, "horizon": 30, "training_cutoff": str(day), "version": "quality_screened_v2"},
                result={"residual_sd": prediction["residual_sd"], "training_rows": prediction["training_rows"],
                        "imputed_rows": prediction["imputed_rows"]})])
        upsert(connection, m.forecasts, rows)
        return {"forecasts": len(rows)}


def verify_impact(engine, action_id: str) -> dict:
    frame = load_mart(engine)
    with engine.begin() as connection:
        action = one(connection, m.actions, action_id)
        existing = records(connection, m.actual_impacts, m.actual_impacts.c.action_id == action_id)
        if existing:
            return {**existing[0], "outcome": one(connection, m.outcomes, action_id)["outcome"]}
        if action["status"] != "SUCCESS":
            raise ValueError("Impact verification requires a successful action")
        recommendation = one(connection, m.recommendations, action["recommendation_id"])
        effective = pd.Timestamp(action["effective_at"]).normalize()
        if frame.timestamp.max().normalize() < effective+pd.Timedelta(days=6):
            return {"status": "WAITING_FOR_DATA", "required_through": str((effective+pd.Timedelta(days=6)).date())}
        if action["action_type"] != "rollback_release":
            return {"status": "UNSUPPORTED_IMPACT_MODEL", "description": "Only rollback has a validated simulator and control design"}
        treatment = (frame.country == action["request_payload"]["country"]) & (frame.device == action["request_payload"]["device"])
        control = (frame.country == action["request_payload"]["country"]) & (frame.device == "Desktop")
        metric = next(r for r in registry() if r.metric_id == "conversion")
        arrays = []
        for mask, start, end in [(treatment, effective-pd.Timedelta(days=7), effective),
                                 (treatment, effective, effective+pd.Timedelta(days=7)),
                                 (control, effective-pd.Timedelta(days=7), effective),
                                 (control, effective, effective+pd.Timedelta(days=7))]:
            daily = aggregate(frame[mask & (frame.timestamp >= start) & (frame.timestamp < end)], metric)
            expected_days = pd.date_range(start, end-pd.Timedelta(days=1))
            daily = daily.set_index("timestamp").reindex(expected_days)
            if daily.actual_value.isna().any():
                return {"status": "WAITING_FOR_DATA", "description": "Incomplete treatment/control observations"}
            arrays.append(daily.actual_value.to_numpy())
        result = measure(*arrays, recommendation["expected_impact"])
        outcome = result.pop("outcome")
        row = dict(id=action_id, action_id=action_id, **result,
                   pre_start=(effective-pd.Timedelta(days=7)).to_pydatetime(),
                   post_end=(effective+pd.Timedelta(days=6)).to_pydatetime())
        upsert(connection, m.actual_impacts, [row])
        upsert(connection, m.outcomes, [dict(id=action_id, action_id=action_id, outcome=outcome,
            description="Synthetic paired-week comparison with Germany desktop control; not a randomized experiment.")])
        learn(connection, recommendation["incident_id"], outcome, result["percentage_impact"])
        connection.execute(update(m.incidents).where(m.incidents.c.id == recommendation["incident_id"]).values(
            status="CLOSED", closed_at=now()))
        return {**row, "outcome": outcome}
