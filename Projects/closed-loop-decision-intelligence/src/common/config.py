"""Validated configuration and secret-safe database URL construction."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


class Settings(BaseModel):
    company: str
    currency: str = "EUR"
    timezone: str = "UTC"
    history_months: int = Field(default=24, ge=12, le=60)
    seed: int = 42
    baseline_days: int = Field(default=56, ge=28)
    approval_ttl_hours: int = Field(default=24, ge=1)
    impact_window_days: int = Field(default=7, ge=3)
    minimum_history_days: int = Field(default=28, ge=14)


def read_config(name: str) -> dict:
    """Read a repository-owned YAML configuration."""
    with (ROOT / "config" / f"{name}.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def settings() -> Settings:
    return Settings(**read_config("settings"))


def offline_url() -> str:
    """Explicit local rehearsal path; configurable without affecting PostgreSQL."""
    return "sqlite:///" + str(ROOT / os.getenv("OFFLINE_DATABASE", "data/generated/offline.db"))


def database_url() -> str | URL:
    if url := os.getenv("DATABASE_URL"):
        return url
    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise ValueError("POSTGRES_PASSWORD is required; run scripts/configure.py")
    return URL.create("postgresql+psycopg", username=os.getenv("POSTGRES_USER", "decision_owner"),
                      password=password, host=os.getenv("POSTGRES_HOST", "localhost"),
                      port=int(os.getenv("POSTGRES_PORT", "5432")),
                      database=os.getenv("POSTGRES_DB", "decision_intelligence"))
