"""Warehouse connections. SQLite is an explicit offline test adapter only."""
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from src.common.config import database_url

SCHEMAS = ("raw", "staging", "analytics", "monitoring", "decision", "audit", "simulation")


def make_engine(url=None) -> Engine:
    engine = create_engine(url or database_url(), pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        engine = engine.execution_options(schema_translate_map=dict.fromkeys(SCHEMAS))

        @event.listens_for(engine, "connect")
        def sqlite_constraints(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


@lru_cache
def get_engine() -> Engine:
    return make_engine()
