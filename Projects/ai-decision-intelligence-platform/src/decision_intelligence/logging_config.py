"""Central logging configuration with safe fallbacks."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from decision_intelligence.settings import ConfigurationError, load_yaml


def configure_logging(config_path: Path, level: str = "INFO") -> None:
    """Configure logging from YAML and apply the requested root level."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ConfigurationError(f"Invalid logging level: {level}")
    config = load_yaml(config_path)
    try:
        logging.config.dictConfig(config)
    except (TypeError, ValueError, AttributeError, ImportError) as exc:
        raise ConfigurationError(f"Invalid logging configuration: {exc}") from exc
    logging.getLogger().setLevel(numeric_level)
