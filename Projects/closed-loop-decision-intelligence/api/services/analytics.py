"""Quality, transformation, KPI and detection application services."""
import logging
import subprocess
import sys
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import select, update

from src.anomaly_detection.detector import detect
from src.common import models as m
from src.common.config import ROOT, read_config
from src.common.store import new_id, now, records, upsert
from src.data_quality.guardian import validate
from src.metrics.engine import load_mart, observations

logger = logging.getLogger(__name__)


@contextmanager
def audit_run(engine, workflow: str):
    run_id = new_id()
    start = now()
    with engine.begin() as connection:
        upsert(connection, m.pipeline_runs, [dict(id=run_id, workflow_name=workflow, start_time=start,
                                                 status="RUNNING", rows_processed=0)])
    result = {"rows_processed": 0}
    try:
        yield result
    except Exception as exc:
        with engine.begin() as connection:
            connection.execute(update(m.pipeline_runs).where(m.pipeline_runs.c.id == run_id).values(
                status="FAILED", end_time=now(), error_message=type(exc).__name__))
            upsert(connection, m.workflow_runs, [dict(id=run_id, run_id=run_id, workflow_name=workflow,
                status="FAILED", details={"error_type": type(exc).__name__})])
        logger.error("Workflow failed", extra={"run_id": run_id, "workflow_name": workflow, "status": "FAILED"})
        raise
    else:
        with engine.begin() as connection:
            connection.execute(update(m.pipeline_runs).where(m.pipeline_runs.c.id == run_id).values(
                status="SUCCESS", end_time=now(), rows_processed=result["rows_processed"]))
            upsert(connection, m.workflow_runs, [dict(id=run_id, run_id=run_id, workflow_name=workflow,
                status="SUCCESS", details=result)])
        logger.info("Workflow finished", extra={"run_id": run_id, "workflow_name": workflow, "status": "SUCCESS"})


def quality(engine, as_of=None):
    frames = {}
    with engine.connect() as connection:
        for table in (m.web_sessions, m.orders, m.payments):
            frames[table.name] = pd.read_sql(select(table), connection)
    report = validate(frames, as_of)
    with engine.begin() as connection:
        upsert(connection, m.data_quality_results, report.checks)
    return report


def transform(engine) -> dict:
    if engine.dialect.name == "sqlite":
        return {"mode": "offline_portable_sql", "dbt_executed": False}
    from pathlib import Path
    executable = Path(sys.executable).parent / ("dbt.exe" if sys.platform == "win32" else "dbt")
    command = [str(executable), "build", "--project-dir", str(ROOT / "dbt"), "--profiles-dir", str(ROOT / "dbt")]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise RuntimeError("dbt build failed. Inspect dbt/logs/dbt.log; warehouse pipeline stopped")
    return {"mode": "postgresql", "dbt_executed": True}


def run_kpis(engine) -> dict:
    with audit_run(engine, "kpi_engine") as run:
        report = quality(engine)
        if report.quarantined:
            raise ValueError("Critical quality failure: dataset quarantined; KPI engine stopped")
        transform(engine)
        frame = load_mart(engine, include_customers=True)
        result = observations(frame)
        rows = result.astype(object).where(pd.notnull(result), None).to_dict("records")
        with engine.begin() as connection:
            upsert(connection, m.metric_observations, rows)
        run["rows_processed"] = len(rows)
    return {"observations": len(rows)}


def detect_anomalies(engine) -> dict:
    with audit_run(engine, "anomaly_detector") as run:
        report = quality(engine)
        if report.quarantined:
            raise ValueError("Critical data-quality failure; anomaly detection stopped")
        with engine.connect() as connection:
            obs = pd.read_sql(select(m.metric_observations), connection)
        if obs.empty:
            raise ValueError("Run KPI engine before detection")
        obs["timestamp"] = pd.to_datetime(obs.timestamp)
        frame = load_mart(engine)
        promotions = set(frame.loc[frame.planned_promotion == 1, "timestamp"].dt.normalize())
        found = detect(obs, report.tracking_days, promotions, frame=frame)
        with engine.begin() as connection:
            upsert(connection, m.anomalies, found)
            existing = records(connection, m.incidents)
            previous = {}
            existing_ids = {i["id"] for i in existing}
            created = []
            scopes = read_config("anomaly_rules")["incident_scopes"]
            for anomaly in sorted(found, key=lambda row: row["timestamp"]):
                # Retain fine-grained anomalies; coalesce incident notifications at chosen actionable scopes.
                if anomaly["dimension_name"] != "all":
                    policy = scopes.get(anomaly["dimension_name"])
                    if not policy or anomaly["metric"] not in policy["metrics"] or anomaly["anomaly_score"] < policy["minimum_score"]:
                        continue
                key = (anomaly["metric"], anomaly["dimension_name"], anomaly["dimension_value"])
                last = previous.get(key)
                previous[key] = anomaly["timestamp"]
                if last is not None and abs((anomaly["timestamp"]-last).days) <= 7:
                    continue
                row = dict(id=anomaly["id"], anomaly_id=anomaly["id"], detected_at=anomaly["timestamp"],
                    metric=anomaly["metric"], problem=f"{anomaly['metric']} deviated {anomaly['deviation']:.1%}; {anomaly['classification']}",
                    severity=anomaly["severity"], dimension_name=anomaly["dimension_name"],
                    dimension_value=anomaly["dimension_value"], driver="unknown", status="OPEN")
                upsert(connection, m.incidents, [row])
                if row["id"] not in existing_ids:
                    created.append(row["id"])
            run["rows_processed"] = len(found)
    return {"anomalies": len(found), "incident_ids": created}
