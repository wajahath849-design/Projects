"""Small transactional repository; parameterized queries only."""
import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.common import models as m
from src.common.db import SCHEMAS


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def identity(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def new_id() -> str:
    return str(uuid4())


def clean(value):
    """Convert pandas/numpy values into JSON-compatible data."""
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def upsert(connection, table, rows: list[dict]) -> int:
    if not rows:
        return 0
    insert = pg_insert if connection.dialect.name == "postgresql" else sqlite_insert
    for offset in range(0, len(rows), 1000):
        statement = insert(table)
        statement = statement.on_conflict_do_nothing(index_elements=["id"])
        connection.execute(statement, rows[offset:offset + 1000])
    return len(rows)


def records(connection, table, condition=None) -> list[dict]:
    query = select(table)
    if condition is not None:
        query = query.where(condition)
    return [dict(row) for row in connection.execute(query).mappings()]


def one(connection, table, record_id: str) -> dict:
    rows = records(connection, table, table.c.id == record_id)
    if not rows:
        raise LookupError(f"{table.name} record not found")
    return rows[0]


def initialize(engine) -> None:
    from src.common.config import ROOT
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            for schema in SCHEMAS:
                connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        m.metadata.create_all(connection)
        sql = (ROOT / "database" / "migrations" / "002_ledger.sql").read_text()
        if engine.dialect.name == "sqlite":
            connection.execute(text("DROP VIEW IF EXISTS v_decision_ledger"))
            sql = sql.replace("CREATE OR REPLACE VIEW", "CREATE VIEW IF NOT EXISTS")
            for schema in SCHEMAS:
                sql = sql.replace(f"{schema}.", "")
        connection.execute(text(sql))
