from datetime import timedelta

from sqlalchemy import select, update

from src.common import models as m
from src.common.config import read_config, settings
from src.common.store import now, one, records, upsert
from src.decision_memory.service import similar


def recommend(connection, incident_id: str) -> dict:
    existing = records(connection, m.recommendations, m.recommendations.c.incident_id == incident_id)
    if existing:
        return existing[0]
    hypothesis = one(connection, m.hypotheses, incident_id)
    config = read_config("decision_rules")
    rule = next((r for r in config["rules"] if r["driver"] == hypothesis["driver"]
                 and hypothesis["confidence"] >= r["minimum_confidence"]), config["fallback"])
    evidence = records(connection, m.evidence, m.evidence.c.incident_id == incident_id)
    row = dict(id=incident_id, incident_id=incident_id, recommendation_type=rule["type"],
        description=f"{rule['type']} based on the {hypothesis['driver']} hypothesis; all actions are simulated.",
        supporting_evidence=[e["id"] for e in evidence[:10]], confidence=hypothesis["confidence"],
        expected_impact=rule["expected_impact"], risk_level=rule["risk"], requires_approval=1,
        memory_context=similar(connection, incident_id))
    upsert(connection, m.recommendations, [row])
    upsert(connection, m.approvals, [dict(id=incident_id, recommendation_id=incident_id, status="PENDING",
        expires_at=now()+timedelta(hours=settings().approval_ttl_hours))])
    upsert(connection, m.expected_impacts, [dict(id=incident_id, recommendation_id=incident_id, metric="conversion",
        expected_percent=row["expected_impact"], window_days=7)])
    return row


def approve(connection, recommendation_id: str, actor: str, accepted: bool, reason: str | None = None) -> dict:
    one(connection, m.recommendations, recommendation_id)
    approval = dict(connection.execute(select(m.approvals).where(
        m.approvals.c.recommendation_id == recommendation_id).with_for_update()).mappings().one())
    target = "APPROVED" if accepted else "REJECTED"
    if approval["status"] == target:
        return approval
    if approval["status"] != "PENDING":
        raise ValueError(f"Cannot change terminal approval state {approval['status']}")
    if approval["expires_at"] < now():
        target = "EXPIRED"
    values = dict(status=target, approved_by=actor, approved_at=now(), rejection_reason=None if accepted else reason)
    connection.execute(update(m.approvals).where(m.approvals.c.id == approval["id"]).values(**values))
    return {**approval, **values}


def execute(connection, recommendation_id: str) -> dict:
    """Lock the approval to serialize duplicate delivery. Never contacts real systems."""
    recommendation = one(connection, m.recommendations, recommendation_id)
    approval = connection.execute(select(m.approvals).where(
        m.approvals.c.recommendation_id == recommendation_id).with_for_update()).mappings().one()
    existing = records(connection, m.actions, m.actions.c.recommendation_id == recommendation_id)
    if existing:
        return existing[0]
    if approval["status"] != "APPROVED":
        raise ValueError("Action requires an explicit, unexpired human approval")
    if approval["expires_at"] < now():
        connection.execute(update(m.approvals).where(m.approvals.c.id == approval["id"]).values(status="EXPIRED"))
        return {"status": "EXPIRED", "recommendation_id": recommendation_id}
    config = read_config("decision_rules")
    rule = next((r for r in config["rules"] if r["type"] == recommendation["recommendation_type"]), config["fallback"])
    from sqlalchemy import func
    watermark = connection.scalar(select(func.max(m.web_sessions.c.timestamp)))
    if watermark is None:
        raise ValueError("No source observations exist")
    incident = one(connection, m.incidents, recommendation["incident_id"])
    scope = {"country": "*", "device": "*"}
    if incident["driver"] == "deployment":
        hypothesis = one(connection, m.hypotheses, incident["id"])
        release_id = hypothesis["signals"]["recent_deployments"][0]
        release = one(connection, m.deployments, release_id)
        scope = {"country": release["country"], "device": release["device"]}
    row = dict(id=recommendation_id, recommendation_id=recommendation_id, action_type=rule["action"],
        status="SUCCESS", execution_time=now(), effective_at=watermark.replace(hour=0, minute=0)+timedelta(days=1),
        request_payload={"simulated": True, "incident_id": incident["id"], **scope},
        response_payload={"accepted": True, "mode": "local_simulator", "source_advanced": False})
    upsert(connection, m.actions, [row])
    return row
