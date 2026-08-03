"""Tests for validated settings loading."""

from pathlib import Path

import pytest

from decision_intelligence.settings import ConfigurationError, load_settings, load_yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_settings_uses_project_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RANDOM_SEED", raising=False)
    app, database = load_settings(PROJECT_ROOT)
    assert app.random_seed == 42
    assert app.environment == "development"
    assert database.database == "AIDecisionIntelligence"
    assert database.trusted_connection is True


def test_environment_overrides_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RANDOM_SEED", "7")
    monkeypatch.setenv("DB_DATABASE", "TestDecisionIntelligence")
    app, database = load_settings(PROJECT_ROOT)
    assert app.random_seed == 7
    assert database.database == "TestDecisionIntelligence"


def test_missing_yaml_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load_yaml(PROJECT_ROOT / "config" / "does_not_exist.yaml")
