"""Explicit opt-in PostgreSQL validation; never silently substitutes SQLite."""
import os

import pytest
from sqlalchemy import text

from src.common.db import make_engine
from src.common.store import initialize


@pytest.mark.postgres
def test_real_postgres_warehouse_and_ledger():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required for real PostgreSQL integration")
    engine = make_engine(url)
    assert engine.dialect.name == "postgresql"
    initialize(engine)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='decision'")) >= 10
        connection.execute(text("SELECT * FROM decision.v_decision_ledger LIMIT 1"))
