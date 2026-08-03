"""FastAPI dependencies kept replaceable for tests and deployments."""

from __future__ import annotations

from decision_intelligence.settings import DatabaseSettings, load_settings


def get_database_settings() -> DatabaseSettings:
    """Return validated database settings for a request."""
    return load_settings()[1]
