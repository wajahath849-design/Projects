from sqlalchemy import text

from src.common import models as m
from src.common.store import one, records, upsert


def similar(connection, incident_id: str) -> list[dict]:
    current = one(connection, m.incidents, incident_id)
    candidates = records(connection, m.incidents, (m.incidents.c.id != incident_id)
                         & (m.incidents.c.status == "CLOSED")
                         & (m.incidents.c.closed_at < current["created_at"])
                         & (m.incidents.c.detected_at < current["detected_at"]))
    result = []
    for item in candidates:
        score = sum(item[key] == current[key] for key in ("metric", "dimension_name", "dimension_value", "driver"))
        if score < 2:
            continue
        recommendation = records(connection, m.recommendations, m.recommendations.c.incident_id == item["id"])
        if not recommendation:
            continue
        action = records(connection, m.actions, m.actions.c.recommendation_id == recommendation[0]["id"])
        outcome = records(connection, m.outcomes, m.outcomes.c.action_id == action[0]["id"]) if action else []
        impact = records(connection, m.actual_impacts, m.actual_impacts.c.action_id == action[0]["id"]) if action else []
        result.append(dict(incident_id=item["id"], similarity=score/4, recommendation=recommendation[0]["recommendation_type"],
                           outcome=outcome[0]["outcome"] if outcome else None,
                           measured_impact=impact[0]["percentage_impact"] if impact else None))
    return sorted(result, key=lambda row: row["similarity"], reverse=True)[:5]


def ledger(connection) -> list[dict]:
    view = "decision.v_decision_ledger" if connection.dialect.name == "postgresql" else "v_decision_ledger"
    return [dict(r) for r in connection.execute(text(f"SELECT * FROM {view} ORDER BY detected_at DESC")).mappings()]


def learn(connection, incident_id: str, outcome: str, effect: float) -> dict:
    incident = one(connection, m.incidents, incident_id)
    lesson = dict(id=incident_id, incident_id=incident_id,
                  lesson=f"{incident['driver']} hypothesis: {outcome}; measured relative effect {effect:.1%}. "
                         "Synthetic comparison only; review control validity before reusing this action.")
    upsert(connection, m.lessons, [lesson])
    return lesson
