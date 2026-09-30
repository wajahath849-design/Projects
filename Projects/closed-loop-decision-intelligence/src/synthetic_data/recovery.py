"""Advance simulated observations only after a recorded, successful intervention.

Uses a paired weekly replay for an inspectable demo, not a real-world experiment.
Every inserted order remains linked to its payment and cohort.
"""
from datetime import timedelta

import numpy as np
from sqlalchemy import select, update

from src.common import models as m
from src.common.store import records, upsert


def advance(connection, action_id: str) -> dict:
    stored = connection.execute(select(m.actions).where(m.actions.c.id == action_id).with_for_update()).mappings().one_or_none()
    if stored is None:
        raise LookupError("Action not found")
    action = dict(stored)
    if action["status"] != "SUCCESS":
        raise ValueError("Only successful simulated actions can advance the simulation")
    if action["response_payload"].get("source_advanced"):
        return action["response_payload"]
    effective = action["effective_at"]
    # Only the rollback demo models a recovery mechanism. Other actions are acknowledgments.
    sessions = records(connection, m.web_sessions, (m.web_sessions.c.timestamp >= effective-timedelta(days=7))
                       & (m.web_sessions.c.timestamp < effective))
    if len(sessions) != 7*126:
        raise ValueError("Seven complete pre-action days are required")
    rng = np.random.default_rng(1234)
    source_ids = [row["id"] for row in sessions]
    order_rows = records(connection, m.orders, m.orders.c.cohort_id.in_(source_ids))
    paid_by_cohort = {}
    old_orders = {r["id"]: r for r in order_rows}
    prefix = f"replay-{action_id[:12]}-"
    def strip(row):
        return {k: v for k, v in row.items() if k not in ("created_at", "updated_at")}
    session_map = {r["id"]: r for r in sessions}
    for target in [m.web_sessions, m.orders, m.payments, m.refunds, m.marketing_campaigns,
                   m.support_tickets, m.subscriptions, m.application_events]:
        if target == m.web_sessions:
            rows = sessions
        elif target == m.orders:
            rows = order_rows
        elif target in (m.payments, m.refunds):
            rows = records(connection, target, target.c.order_id.in_(list(old_orders)))
        else:
            rows = records(connection, target, target.c.cohort_id.in_(source_ids))
        output = []
        for source in rows:
            row = strip(source)
            row["id"] = prefix+row["id"]
            if "timestamp" in row:
                row["timestamp"] += timedelta(days=7)
            cohort_id = source.get("cohort_id", source["id"])
            if "order_id" in source:
                cohort_id = old_orders[source["order_id"]]["cohort_id"]
            scope = session_map.get(cohort_id, {})
            treatment = scope.get("country") == action["request_payload"]["country"] and scope.get("device") == action["request_payload"]["device"]
            rollback = treatment and action["action_type"] == "rollback_release"
            if target == m.orders:
                if rollback:
                    row["status"] = "PAID" if rng.random() > .03 else "FAILED"
                row["is_new"] = 0
                paid_by_cohort[source["id"]] = row["status"]
            elif target == m.payments:
                row["status"] = paid_by_cohort[source["order_id"]]
            elif target == m.refunds and paid_by_cohort[source["order_id"]] != "PAID":
                continue
            elif target == m.application_events and rollback:
                row["checkout_errors"] = 0
                row["latency_ms"] = 210.
            for key in ("cohort_id", "order_id"):
                if key in row:
                    row[key] = prefix+row[key]
            output.append(row)
        upsert(connection, target, output)
    response = {**action["response_payload"], "source_advanced": True, "post_days": 7,
                "recovery_model": "paired_week_replay", "seed": 1234}
    connection.execute(update(m.actions).where(m.actions.c.id == action_id).values(response_payload=response))
    return response
