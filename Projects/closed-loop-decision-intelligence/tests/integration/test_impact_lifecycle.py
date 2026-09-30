from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, select

from api.services.decisions import verify_impact
from src.common import models as m
from src.common.db import make_engine
from src.common.store import initialize, now, upsert
from src.decision_memory.service import ledger


def test_impact_waits_for_complete_windows_and_closes_once(tmp_path, monkeypatch):
    engine = make_engine("sqlite:///"+str(tmp_path/"impact.db"))
    initialize(engine)
    effective = datetime(2026, 2, 8)
    with engine.begin() as connection:
        upsert(connection, m.incidents, [dict(id="i", detected_at=effective-timedelta(days=7), metric="conversion",
            problem="Checkout regression", severity="HIGH", dimension_name="country_device",
            dimension_value="Germany / Mobile", driver="deployment", status="INVESTIGATED")])
        upsert(connection, m.recommendations, [dict(id="r", incident_id="i", recommendation_type="ROLLBACK",
            description="Synthetic rollback", supporting_evidence=[], confidence=.9, expected_impact=.2,
            risk_level="HIGH", requires_approval=1, memory_context=[])])
        upsert(connection, m.actions, [dict(id="a", recommendation_id="r", action_type="rollback_release",
            status="SUCCESS", execution_time=now(), effective_at=effective,
            request_payload={"country": "Germany", "device": "Mobile"}, response_payload={"simulated": True})])
    rows = []
    for day in pd.date_range("2026-02-01", periods=14):
        for device in ["Mobile", "Desktop"]:
            rows.append(dict(timestamp=day, country="Germany", device=device,
                             orders=30 if device == "Mobile" and day >= effective else 20, sessions=1000))
    frame = pd.DataFrame(rows)
    monkeypatch.setattr("api.services.decisions.load_mart", lambda _: frame.iloc[:-2])
    assert verify_impact(engine, "a")["status"] == "WAITING_FOR_DATA"
    monkeypatch.setattr("api.services.decisions.load_mart", lambda _: frame)
    assert verify_impact(engine, "a")["outcome"] == "SUCCESS"
    assert verify_impact(engine, "a")["outcome"] == "SUCCESS"
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(m.actual_impacts)) == 1
        row = ledger(connection)[0]
        assert row["closed_at"] is not None and row["lesson"]
