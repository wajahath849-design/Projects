"""Individually callable stages for n8n; the CLI is a local rehearsal adapter."""
from datetime import timedelta

from sqlalchemy import func, select

from api.services.analytics import audit_run, detect_anomalies, quality, run_kpis, transform
from api.services.decisions import forecast_incident, investigate_incident, verify_impact
from src.common import models as m
from src.common.store import records
from src.decision_engine.service import execute, recommend
from src.decision_memory.service import ledger
from src.ingestion.loader import ingest
from src.metrics.engine import load_mart
from src.synthetic_data.generator import generate
from src.synthetic_data.recovery import advance

STAGES = ["ingestion", "quality", "kpis", "anomalies", "investigation", "forecast", "decisions",
          "approvals", "actions", "impact", "memory"]


def stage(engine, name: str) -> dict:
    if name not in STAGES:
        raise ValueError("Unknown workflow stage")
    with audit_run(engine, name) as audit:
        result = _stage(engine, name)
        audit["rows_processed"] = result.get("processed", 0)
        return {"stage": name, **result}


def _stage(engine, name):
    if name == "ingestion":
        with engine.connect() as connection:
            populated = connection.scalar(select(func.count()).select_from(m.web_sessions))
        if populated:
            return {"status": "SOURCE_ALREADY_LOADED", "processed": 0}
        frames, truth = generate()
        counts = ingest(engine, frames, truth)
        return {"status": "SUCCESS", "processed": sum(counts.values()), "tables": counts}
    if name == "quality":
        result = quality(engine)
        if result.quarantined:
            raise ValueError("QUARANTINED: critical source quality failure; downstream stages stopped")
        return {"status": "PASS", "tracking_days": len(result.tracking_days), "processed": len(result.checks)}
    if name == "kpis":
        return run_kpis(engine)
    if name == "anomalies":
        return detect_anomalies(engine)
    if name in ("investigation", "forecast", "decisions"):
        with engine.connect() as connection:
            incidents = records(connection, m.incidents)
        frame = load_mart(engine) if name != "decisions" else None
        count = 0
        for incident in incidents:
            if name == "investigation":
                investigate_incident(engine, incident["id"], frame)
            elif name == "forecast":
                # Forecast current incidents on schedule; historical forecasts remain available on demand.
                if incident["detected_at"] < frame.timestamp.max().to_pydatetime()-timedelta(days=14):
                    continue
                forecast_incident(engine, incident["id"], frame)
            else:
                with engine.begin() as connection:
                    recommend(connection, incident["id"])
            count += 1
        return {"processed": count, "status": "SUCCESS"}
    if name == "approvals":
        with engine.connect() as connection:
            rows = records(connection, m.approvals, (m.approvals.c.status == "APPROVED") &
                           ~m.approvals.c.recommendation_id.in_(select(m.actions.c.recommendation_id)))
        return {"processed": len(rows), "status": "APPROVED" if rows else "WAITING_FOR_HUMAN"}
    if name == "actions":
        with engine.begin() as connection:
            approvals = records(connection, m.approvals, (m.approvals.c.status == "APPROVED") &
                                ~m.approvals.c.recommendation_id.in_(select(m.actions.c.recommendation_id)))
            rows = [execute(connection, a["recommendation_id"]) for a in approvals]
        return {"processed": len(rows), "status": "SUCCESS", "action_ids": [a["id"] for a in rows if "id" in a]}
    if name == "impact":
        with engine.connect() as connection:
            actions = records(connection, m.actions, m.actions.c.status == "SUCCESS")
        results = [verify_impact(engine, a["id"]) for a in actions]
        return {"processed": len(results), "results": results}
    with engine.connect() as connection:
        rows = ledger(connection)
    return {"processed": len(rows), "closed": sum(r["closed_at"] is not None for r in rows)}


def run_pipeline(engine) -> list[dict]:
    """Stop at human approval. Never approves or executes actions implicitly."""
    return [stage(engine, name) for name in STAGES[1:7]]


def advance_simulation(engine, action_id: str) -> dict:
    with engine.begin() as connection:
        result = advance(connection, action_id)
    transform(engine)
    return result
