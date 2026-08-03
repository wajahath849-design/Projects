"""Tests for logging configuration."""

import logging
from pathlib import Path

import pytest

from decision_intelligence.logging_config import configure_logging
from decision_intelligence.settings import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_logging_configuration_sets_requested_level() -> None:
    configure_logging(PROJECT_ROOT / "config" / "logging.yaml", "DEBUG")
    assert logging.getLogger().level == logging.DEBUG


def test_invalid_logging_level_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="Invalid logging level"):
        configure_logging(PROJECT_ROOT / "config" / "logging.yaml", "LOUD")
