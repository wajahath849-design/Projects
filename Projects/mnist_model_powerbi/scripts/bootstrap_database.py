from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re

import pyodbc

from app import config
from app.db import connection_string
from app.model_registry import read_model_configs, sync_registry

ROOT = Path(__file__).resolve().parents[1]
GO = re.compile(r"^\s*GO\s*(?:--.*)?$", re.IGNORECASE | re.MULTILINE)


def execute_file(connection, path: Path) -> None:
    for batch in GO.split(path.read_text(encoding="utf-8-sig")):
        if batch.strip():
            connection.cursor().execute(batch)


def main() -> None:
    print(f"Preparing {config.DB_NAME} on {config.DB_SERVER} with Windows Authentication...")
    with pyodbc.connect(connection_string("master"), autocommit=True) as connection:
        database_exists = bool(
            connection.cursor().execute("SELECT DB_ID(?)", config.DB_NAME).fetchone()[0]
        )

    core_schema_exists = False
    if database_exists:
        with pyodbc.connect(connection_string(config.DB_NAME), autocommit=True) as connection:
            core_schema_exists = bool(
                connection.cursor().execute(
                    """SELECT CASE WHEN OBJECT_ID(N'dbo.ModelRegistry', N'U') IS NOT NULL
                                      AND OBJECT_ID(N'dbo.ImageBatch', N'U') IS NOT NULL
                                      AND OBJECT_ID(N'dbo.ModelPrediction', N'U') IS NOT NULL
                                   THEN 1 ELSE 0 END"""
                ).fetchone()[0]
            )

    # 001 is intentionally a clean-install schema and drops project tables. Never
    # run it over an existing installation with user prediction history.
    if not core_schema_exists:
        with pyodbc.connect(connection_string("master"), autocommit=True) as connection:
            execute_file(connection, ROOT / "database" / "001_clean_schema.sql")
        print("Created the clean database schema.")
    else:
        print("Existing database detected; preserving prediction history.")

    # Column migrations must run before the reporting views that reference them.
    migration_order = (
        "003_processed_image_preview.sql",
        "004_pipeline_metrics_version.sql",
        "002_reporting_views.sql",
    )
    with pyodbc.connect(connection_string("master"), autocommit=True) as connection:
        for filename in migration_order:
            execute_file(connection, ROOT / "database" / filename)
    sync_registry(read_model_configs())
    with pyodbc.connect(connection_string(config.DB_NAME), autocommit=True) as connection:
        cursor = connection.cursor()
        tables = {row[0] for row in cursor.execute("SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')")}
        views = {row[0] for row in cursor.execute("SELECT name FROM sys.views WHERE schema_id=SCHEMA_ID('dbo')")}
    required_tables = {"ModelRegistry","ImageBatch","ModelPrediction","ClassProbability","HumanReview","SystemEvent"}
    required_views = {"vw_PredictionHistoryAll","vw_PredictionDetail","vw_LatestCompletedImage","vw_LatestBatchSummary","vw_ModelPerformance","vw_ModelAgreement","vw_ConfusionMatrix","vw_ClassPerformance","vw_DailyProcessingTrend","vw_FailedPredictions","vw_HumanReviewQueue","vw_SystemHealth"}
    missing = sorted((required_tables - tables) | (required_views - views))
    if missing:
        raise SystemExit("Database build failed; missing objects: " + ", ".join(missing))
    print("Database schema, registry and reporting views are ready.")


if __name__ == "__main__":
    main()
