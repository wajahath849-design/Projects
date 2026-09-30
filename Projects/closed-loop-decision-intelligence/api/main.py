"""Authenticated FastAPI boundary with separate human-approval credentials."""
import hmac
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.schemas import ApprovalInput
from api.services import analytics, decisions, orchestration
from api.services.operations import operating_metrics
from src.common import models as m
from src.common.db import get_engine
from src.common.logging import configure_logging
from src.common.store import initialize, one, records, upsert
from src.decision_engine.service import approve, execute, recommend
from src.decision_memory.service import ledger, similar


@asynccontextmanager
async def lifespan(app):
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    initialize(get_engine())
    yield


app = FastAPI(title="Closed-Loop Decision Intelligence", version="0.1.0", lifespan=lifespan)


def authorized(x_api_key: Annotated[str | None, Header()] = None):
    expected = os.getenv("API_TOKEN", "")
    if not expected or not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Valid X-API-Key required")


def human(x_approval_token: Annotated[str | None, Header()] = None):
    expected = os.getenv("APPROVAL_TOKEN", "")
    if not expected or not x_approval_token or not hmac.compare_digest(x_approval_token, expected):
        raise HTTPException(403, "Separate X-Approval-Token required for human decisions")


Auth = Depends(authorized)
Human = Depends(human)


@app.exception_handler(LookupError)
async def missing(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.middleware("http")
async def audit_request(request: Request, call_next):
    start = time.perf_counter()
    request_id = str(uuid4())
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        if request.url.path != "/health":
            try:
                with get_engine().begin() as connection:
                    upsert(connection, m.api_requests, [dict(id=request_id, request_id=request_id, method=request.method,
                        path=request.url.path, status_code=status_code, duration_ms=(time.perf_counter()-start)*1000)])
            except SQLAlchemyError:
                logging.getLogger(__name__).error("API audit storage unavailable", extra={"run_id": request_id})


@app.get("/health")
def health():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Warehouse unavailable")
    return {"status": "healthy", "action_mode": "simulation", "warehouse_dialect": get_engine().dialect.name}


@app.post("/analytics/run-kpis", dependencies=[Auth])
def kpis():
    return analytics.run_kpis(get_engine())


@app.post("/analytics/detect-anomalies", dependencies=[Auth])
def anomalies():
    return analytics.detect_anomalies(get_engine())


@app.post("/analytics/investigate/{anomaly_id}", dependencies=[Auth])
def investigate(anomaly_id: str):
    return decisions.investigate_incident(get_engine(), anomaly_id)


@app.post("/analytics/forecast/{incident_id}", dependencies=[Auth])
def forecast(incident_id: str):
    return decisions.forecast_incident(get_engine(), incident_id)


@app.post("/decisions/recommend/{incident_id}", dependencies=[Auth])
def recommendation(incident_id: str):
    with get_engine().begin() as connection:
        return recommend(connection, incident_id)


@app.get("/incidents", dependencies=[Auth])
def incidents():
    with get_engine().connect() as connection:
        return records(connection, m.incidents)


@app.get("/incidents/{incident_id}", dependencies=[Auth])
def incident(incident_id: str):
    with get_engine().connect() as connection:
        return {**one(connection, m.incidents, incident_id),
                "evidence": records(connection, m.evidence, m.evidence.c.incident_id == incident_id)}


@app.get("/recommendations/{recommendation_id}", dependencies=[Auth])
def get_recommendation(recommendation_id: str):
    with get_engine().connect() as connection:
        return {**one(connection, m.recommendations, recommendation_id),
                "approval": one(connection, m.approvals, recommendation_id)}


@app.post("/recommendations/{recommendation_id}/approve", dependencies=[Auth, Human])
def approve_recommendation(recommendation_id: str, body: ApprovalInput):
    with get_engine().begin() as connection:
        return approve(connection, recommendation_id, body.actor, True)


@app.post("/recommendations/{recommendation_id}/reject", dependencies=[Auth, Human])
def reject_recommendation(recommendation_id: str, body: ApprovalInput):
    if not body.reason:
        raise HTTPException(422, "A rejection reason is required")
    with get_engine().begin() as connection:
        return approve(connection, recommendation_id, body.actor, False, body.reason)


@app.post("/actions/execute/{recommendation_id}", dependencies=[Auth])
def action(recommendation_id: str):
    with get_engine().begin() as connection:
        return execute(connection, recommendation_id)


@app.post("/simulation/advance/{action_id}", dependencies=[Auth])
def advance(action_id: str):
    return orchestration.advance_simulation(get_engine(), action_id)


@app.post("/impact/verify/{action_id}", dependencies=[Auth])
def impact(action_id: str):
    return decisions.verify_impact(get_engine(), action_id)


@app.get("/decision-ledger", dependencies=[Auth])
def get_ledger():
    with get_engine().connect() as connection:
        return ledger(connection)


@app.get("/decision-memory/similar/{incident_id}", dependencies=[Auth])
def memory(incident_id: str):
    with get_engine().connect() as connection:
        return similar(connection, incident_id)


@app.post("/orchestration/{stage}", dependencies=[Auth])
def orchestrate(stage: str):
    return orchestration.stage(get_engine(), stage)


@app.get("/operations/kpis", dependencies=[Auth])
def operations():
    with get_engine().connect() as connection:
        return operating_metrics(connection)
