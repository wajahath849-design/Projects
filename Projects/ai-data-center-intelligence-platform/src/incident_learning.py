"""Human-controlled incident review and knowledge-candidate lifecycle."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.incident_engine import InvestigationResult


class IncidentLearningLoop:
    REVIEWER_ROLES = {
        "incident_manager", "operations_engineer", "network_engineer",
        "facilities_engineer", "hardware_technician", "application_engineer",
        "simulation_reviewer",
    }

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def propose(self, investigation: InvestigationResult) -> str:
        review_id = f"REVIEW-{uuid.uuid4().hex[:12].upper()}"
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """INSERT INTO incident_reviews (
                    review_id, incident_id, created_at, review_status,
                    ai_hypothesis, ai_confidence, knowledge_update_status, simulation
                ) VALUES (?, ?, ?, 'pending', ?, ?, 'not_eligible', 0)""",
                (
                    review_id, investigation.incident_id, created_at,
                    investigation.answer, investigation.diagnostic_confidence,
                ),
            )
        return review_id

    def review(
        self,
        review_id: str,
        confirmed: bool,
        reviewer_role: str,
        root_cause: str | None,
        resolution_notes: str,
        simulation: bool = False,
    ) -> None:
        if reviewer_role not in self.REVIEWER_ROLES:
            raise ValueError("Reviewer role is not allowed")
        if confirmed and not (root_cause or "").strip():
            raise ValueError("A human-confirmed root cause is required for confirmation")
        if not resolution_notes.strip():
            raise ValueError("Human resolution notes are required")
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status = "confirmed" if confirmed else "rejected"
        knowledge_status = "pending_review" if confirmed else "rejected"
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """UPDATE incident_reviews
                SET review_status=?, human_confirmed_root_cause=?, resolution_notes=?,
                    reviewed_by_role=?, reviewed_at=?, knowledge_update_status=?, simulation=?
                WHERE review_id=? AND review_status='pending'""",
                (
                    status, root_cause.strip() if confirmed and root_cause else None,
                    resolution_notes.strip(), reviewer_role, reviewed_at,
                    knowledge_status, int(simulation), review_id,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError("Pending review not found or already reviewed")

    def decide_knowledge_update(
        self, review_id: str, approve: bool, reviewer_role: str
    ) -> None:
        if reviewer_role not in self.REVIEWER_ROLES:
            raise ValueError("Reviewer role is not allowed")
        status = "approved" if approve else "rejected"
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                """UPDATE incident_reviews SET knowledge_update_status=?
                WHERE review_id=? AND review_status='confirmed'
                  AND knowledge_update_status='pending_review'""",
                (status, review_id),
            )
            if cursor.rowcount != 1:
                raise LookupError("Confirmed review awaiting knowledge decision was not found")

    def approved_candidates(self) -> list[dict[str, object]]:
        with sqlite3.connect(f"file:{self.database_path.resolve().as_posix()}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only = ON")
            return [dict(row) for row in connection.execute(
                """SELECT r.*, i.facility_id, i.server_id, i.start_time,
                    i.root_cause AS original_root_cause
                FROM incident_reviews AS r
                JOIN uptime_incidents AS i ON i.incident_id=r.incident_id
                WHERE r.review_status='confirmed' AND r.knowledge_update_status='approved'
                ORDER BY r.reviewed_at, r.review_id"""
            ).fetchall()]
