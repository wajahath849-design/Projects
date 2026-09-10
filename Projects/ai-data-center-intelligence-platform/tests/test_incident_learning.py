import sqlite3
from pathlib import Path

import pytest

from src.incident_learning import IncidentLearningLoop


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


def test_seeded_reviews_are_explicit_simulations_and_human_confirmed() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        rows = connection.execute(
            """SELECT review_status, knowledge_update_status, simulation,
                human_confirmed_root_cause, reviewed_by_role
            FROM incident_reviews"""
        ).fetchall()
    assert len(rows) == 6
    assert all(row[0] == "confirmed" and row[1] == "approved" for row in rows)
    assert all(row[2] == 1 and row[3] and row[4] == "simulation_reviewer" for row in rows)


def test_only_confirmed_approved_reviews_become_candidates() -> None:
    candidates = IncidentLearningLoop(DATABASE).approved_candidates()
    assert len(candidates) == 6
    assert all(item["review_status"] == "confirmed" for item in candidates)
    assert all(item["knowledge_update_status"] == "approved" for item in candidates)
    assert all(item["simulation"] == 1 for item in candidates)


def test_invalid_reviewer_role_is_rejected() -> None:
    with pytest.raises(ValueError):
        IncidentLearningLoop(DATABASE).review(
            "REVIEW-MISSING", True, "anonymous_user", "hardware failure", "notes"
        )
