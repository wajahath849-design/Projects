"""Static checks for Docker, Compose, automation, and CI assets."""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_docker_and_compose_assets_are_valid() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    assert {"api", "sqlserver", "sql-init"} <= set(compose["services"])
    assert compose["services"]["sqlserver"]["profiles"] == ["container-sql"]


def test_ci_runs_full_critical_pipeline() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    for command in (
        "train_models.py", "calculate_inventory_intelligence.py", "run_optimization.py",
        "run_scenarios.py", "export_power_bi_data.py", "pytest", "ruff", "mypy",
    ):
        assert command in workflow
    assert "CI_SQL_PASSWORD" in workflow
