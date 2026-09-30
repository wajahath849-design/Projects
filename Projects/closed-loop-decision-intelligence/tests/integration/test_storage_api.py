from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from api.main import app
from src.common import models as m
from src.common.db import make_engine
from src.common.store import initialize, now, upsert
from src.decision_engine.service import approve, execute


@pytest.fixture
def warehouse(tmp_path):
    engine = make_engine("sqlite:///"+str(tmp_path/"test.db"))
    initialize(engine)
    yield engine
    engine.dispose()


def seed_recommendation(engine):
    with engine.begin() as connection:
        upsert(connection, m.web_sessions, [dict(id="source", timestamp=now(), country="Germany", device="Mobile",
            channel="Direct", product_category="Software", customer_segment="Consumer", sessions=100,
            server_sessions=100, planned_promotion=0)])
        upsert(connection, m.incidents, [dict(id="i1", detected_at=now(), metric="conversion", problem="decline",
            severity="HIGH", dimension_name="country_device", dimension_value="Germany / Mobile", driver="unknown", status="OPEN")])
        upsert(connection, m.recommendations, [dict(id="r1", incident_id="i1", recommendation_type="INVESTIGATE",
            description="Review evidence", supporting_evidence=[], confidence=.8, expected_impact=.1,
            risk_level="LOW", requires_approval=1, memory_context=[])])
        upsert(connection, m.approvals, [dict(id="r1", recommendation_id="r1", status="PENDING", expires_at=now()+timedelta(hours=1))])


def test_approval_gate_idempotency_rejection_and_expiry(warehouse):
    seed_recommendation(warehouse)
    with warehouse.begin() as connection:
        with pytest.raises(ValueError, match="explicit"):
            execute(connection, "r1")
        approve(connection, "r1", "test-human", True)
        first = execute(connection, "r1")
        second = execute(connection, "r1")
        assert first["id"] == second["id"]
        assert connection.scalar(select(func.count()).select_from(m.actions)) == 1
        with pytest.raises(ValueError, match="terminal"):
            approve(connection, "r1", "test-human", False, "changed mind")


def test_expired_cannot_execute(warehouse):
    seed_recommendation(warehouse)
    with warehouse.begin() as connection:
        connection.execute(update(m.approvals).values(expires_at=now()-timedelta(seconds=1)))
        result = approve(connection, "r1", "test-human", True)
        assert result["status"] == "EXPIRED"
        with pytest.raises(ValueError):
            execute(connection, "r1")


def test_rejected_recommendation_never_executes(warehouse):
    seed_recommendation(warehouse)
    with warehouse.begin() as connection:
        result = approve(connection, "r1", "test-human", False, "Evidence is insufficient")
        assert result["status"] == "REJECTED"
        with pytest.raises(ValueError):
            execute(connection, "r1")
        assert connection.scalar(select(func.count()).select_from(m.actions)) == 0


def test_api_auth_and_human_separation(warehouse, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-service-token")
    monkeypatch.setenv("APPROVAL_TOKEN", "test-human-token")
    monkeypatch.setattr("api.main.get_engine", lambda: warehouse)
    seed_recommendation(warehouse)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/incidents").status_code == 401
        headers = {"X-API-Key": "test-service-token"}
        assert client.get("/incidents", headers=headers).status_code == 200
        assert client.post("/actions/execute/r1", headers=headers).status_code == 409
        assert client.post("/recommendations/r1/approve", headers=headers, json={"actor": "operator"}).status_code == 403
        headers["X-Approval-Token"] = "test-human-token"
        assert client.post("/recommendations/r1/approve", headers=headers, json={"actor": "operator"}).status_code == 200
        assert client.post("/actions/execute/r1", headers=headers).json()["status"] == "SUCCESS"
        assert client.get("/recommendations/missing", headers=headers).status_code == 404
        assert client.get("/decision-ledger", headers=headers).json()[0]["approval_status"] == "APPROVED"
