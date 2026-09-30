import json
import logging

from src.common.config import database_url, settings
from src.common.logging import JsonFormatter


def test_config_validation():
    assert settings().history_months == 24


def test_database_password_escaping(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")
    assert database_url().password == "p@ss/word"
    assert "p@ss/word" not in str(database_url())


def test_structured_log():
    record = logging.LogRecord("pipeline", logging.INFO, "", 0, "finished", (), None)
    record.run_id = "r1"
    assert json.loads(JsonFormatter().format(record))["run_id"] == "r1"
