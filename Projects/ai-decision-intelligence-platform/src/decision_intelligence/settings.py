"""Validated YAML and environment configuration loading."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when configuration is missing or invalid."""


@dataclass(frozen=True)
class AppSettings:
    """Runtime settings shared by platform components."""

    project_root: Path
    environment: str
    log_level: str
    random_seed: int
    config_dir: Path
    model_artifact_path: Path
    mlflow_tracking_uri: str


@dataclass(frozen=True)
class DatabaseSettings:
    """SQL Server connection settings without credentials."""

    server: str
    database: str
    driver: str
    trusted_connection: bool
    trust_server_certificate: bool
    connection_timeout_seconds: int
    command_timeout_seconds: int
    username: str | None = None
    password: str | None = None


def _as_bool(value: object, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{field_name} must be a boolean value")


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping and reject missing, empty, or malformed files."""
    if not path.is_file():
        raise ConfigurationError(f"Configuration file not found: {path}")
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Unable to load configuration file {path}: {exc}") from exc
    if not isinstance(content, Mapping):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return dict(content)


def load_settings(project_root: Path | None = None) -> tuple[AppSettings, DatabaseSettings]:
    """Load settings from YAML, overridden by environment variables."""
    root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    load_dotenv(root / ".env", override=False)
    config_dir = (root / os.getenv("APP_CONFIG_DIR", "config")).resolve()
    app_config = load_yaml(config_dir / "app.yaml").get("app")
    db_config = load_yaml(config_dir / "database.yaml").get("database")
    if not isinstance(app_config, Mapping) or not isinstance(db_config, Mapping):
        raise ConfigurationError("Both app and database configuration sections are required")
    try:
        seed = int(os.getenv("RANDOM_SEED", str(app_config["random_seed"])))
    except (KeyError, ValueError) as exc:
        raise ConfigurationError("RANDOM_SEED must be an integer") from exc
    if seed < 0:
        raise ConfigurationError("RANDOM_SEED must be non-negative")
    app = AppSettings(
        project_root=root,
        environment=os.getenv("APP_ENV", str(app_config["environment"])),
        log_level=os.getenv("APP_LOG_LEVEL", "INFO").upper(),
        random_seed=seed,
        config_dir=config_dir,
        model_artifact_path=root / os.getenv("MODEL_ARTIFACT_PATH", "models/artifacts"),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "mlruns"),
    )
    database = DatabaseSettings(
        server=os.getenv("DB_SERVER", str(db_config["server"])),
        database=os.getenv("DB_DATABASE", str(db_config["name"])),
        driver=os.getenv("DB_DRIVER", str(db_config["driver"])),
        trusted_connection=_as_bool(
            os.getenv("DB_TRUSTED_CONNECTION", str(db_config["trusted_connection"])),
            "DB_TRUSTED_CONNECTION",
        ),
        trust_server_certificate=_as_bool(
            os.getenv("DB_TRUST_SERVER_CERTIFICATE", str(db_config["trust_server_certificate"])),
            "DB_TRUST_SERVER_CERTIFICATE",
        ),
        connection_timeout_seconds=int(
            os.getenv("DB_CONNECTION_TIMEOUT_SECONDS", str(db_config["connection_timeout_seconds"]))
        ),
        command_timeout_seconds=int(
            os.getenv("DB_COMMAND_TIMEOUT_SECONDS", str(db_config["command_timeout_seconds"]))
        ),
        username=os.getenv("DB_USERNAME") or None,
        password=os.getenv("DB_PASSWORD") or None,
    )
    if database.connection_timeout_seconds <= 0 or database.command_timeout_seconds <= 0:
        raise ConfigurationError("Database timeouts must be positive integers")
    if not database.trusted_connection and not (database.username and database.password):
        raise ConfigurationError(
            "DB_USERNAME and DB_PASSWORD are required when trusted connection is disabled"
        )
    return app, database
