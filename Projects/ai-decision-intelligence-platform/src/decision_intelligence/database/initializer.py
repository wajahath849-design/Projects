"""Idempotent database schema initialization and verification."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

import pyodbc

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import DatabaseSettings

LOGGER = logging.getLogger(__name__)
GO_PATTERN = re.compile(r"^\s*GO(?:\s+(\d+))?\s*(?:--.*)?$", re.IGNORECASE)

EXPECTED_TABLES = frozenset(
    {
        "DimDate",
        "DimProduct",
        "DimCategory",
        "DimStore",
        "DimState",
        "DimWarehouse",
        "DimSupplier",
        "DimScenario",
        "DimModel",
        "FactSales",
        "FactSellPrice",
        "FactInventorySnapshot",
        "FactPurchaseOrder",
        "FactPurchaseOrderLine",
        "FactSupplierPerformance",
        "FactTransportation",
        "FactForecast",
        "FactForecastMetric",
        "FactModelRun",
        "FactModelExplanation",
        "FactStockoutRisk",
        "FactOptimizationRecommendation",
        "FactOptimizationAllocation",
        "FactScenarioResult",
        "FactDataQuality",
    }
)
EXPECTED_VIEWS = frozenset(
    {
        "vw_ExecutiveOverview",
        "vw_DemandForecast",
        "vw_InventoryIntelligence",
        "vw_OptimizationRecommendations",
        "vw_ScenarioComparison",
        "vw_ModelPerformance",
        "vw_DataQualitySummary",
        "vw_ProductDecisionDetail",
    }
)


@dataclass(frozen=True)
class VerificationResult:
    """Detailed database verification outcome."""

    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


def split_sql_batches(sql: str) -> list[str]:
    """Split SQL Server scripts on standalone GO directives, including repeats."""
    batches: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        match = GO_PATTERN.match(line)
        if not match:
            current.append(line)
            continue
        batch = "\n".join(current).strip()
        if batch:
            batches.extend([batch] * int(match.group(1) or "1"))
        current = []
    final_batch = "\n".join(current).strip()
    if final_batch:
        batches.append(final_batch)
    return batches


def execute_script(connection: pyodbc.Connection, path: Path) -> None:
    """Execute every non-empty batch from a UTF-8 SQL file."""
    try:
        script = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise RuntimeError(f"Unable to read SQL script {path}: {exc}") from exc
    batches = split_sql_batches(script)
    if not batches:
        raise ValueError(f"SQL script contains no executable batches: {path}")
    LOGGER.info("Executing %s (%d batches)", path.name, len(batches))
    cursor = connection.cursor()
    for number, batch in enumerate(batches, start=1):
        try:
            cursor.execute(batch)
            while cursor.nextset():
                pass
        except pyodbc.Error as exc:
            raise RuntimeError(f"{path.name} failed in batch {number}: {exc}") from exc


def initialize_database(
    settings: DatabaseSettings,
    schema_directory: Path,
    seed_directory: Path,
) -> None:
    """Create the database, apply ordered schema scripts, and insert minimal seeds."""
    scripts = sorted(schema_directory.glob("[0-9][0-9][0-9]_*.sql"))
    seeds = sorted(seed_directory.glob("[0-9][0-9][0-9]_*.sql"))
    if len(scripts) != 7:
        raise RuntimeError(f"Expected 7 schema scripts, found {len(scripts)}")
    with connect(settings, "master", autocommit=True) as master:
        execute_script(master, scripts[0])
    with connect(settings, settings.database) as database:
        try:
            for script in scripts[1:]:
                execute_script(database, script)
            for seed in seeds:
                execute_script(database, seed)
            database.commit()
        except Exception:
            database.rollback()
            raise


def verify_database(settings: DatabaseSettings) -> VerificationResult:
    """Verify objects, constraints, indexes, seeds, and a rolled-back test insert."""
    checks: list[str] = []
    failures: list[str] = []
    with connect(settings) as connection:
        database_name = fetch_scalar(connection, "SELECT DB_NAME()")
        if database_name == settings.database:
            checks.append(f"database={database_name}")
        else:
            failures.append(f"Connected to {database_name}, expected {settings.database}")
        tables = {row[0] for row in connection.execute("SELECT name FROM sys.tables")}
        views = {row[0] for row in connection.execute("SELECT name FROM sys.views")}
        missing_tables = EXPECTED_TABLES - tables
        missing_views = EXPECTED_VIEWS - views
        if missing_tables:
            failures.append(f"Missing tables: {sorted(missing_tables)}")
        else:
            checks.append(f"tables={len(EXPECTED_TABLES)}")
        if missing_views:
            failures.append(f"Missing views: {sorted(missing_views)}")
        else:
            checks.append(f"views={len(EXPECTED_VIEWS)}")
        foreign_keys = int(fetch_scalar(connection, "SELECT COUNT(*) FROM sys.foreign_keys"))
        indexes = int(
            fetch_scalar(
                connection,
                """
                SELECT COUNT(*)
                FROM sys.indexes AS i
                JOIN sys.tables AS t ON t.object_id = i.object_id
                WHERE i.is_primary_key = 0 AND i.name IS NOT NULL
                """,
            )
        )
        if foreign_keys >= 25:
            checks.append(f"foreign_keys={foreign_keys}")
        else:
            failures.append(f"Only {foreign_keys} foreign keys found")
        if indexes >= 20:
            checks.append(f"secondary_indexes={indexes}")
        else:
            failures.append(f"Only {indexes} secondary indexes found")
        seed_count = int(fetch_scalar(connection, "SELECT COUNT(*) FROM dbo.DimModel"))
        if seed_count >= 3:
            checks.append(f"model_seeds={seed_count}")
        else:
            failures.append("Minimal model seeds are missing")
        test_id = f"VERIFY_{uuid.uuid4().hex[:12]}"
        try:
            connection.execute(
                "INSERT dbo.DimCategory (CategoryID, CategoryName, SourceSystem) VALUES (?, ?, ?)",
                test_id,
                "Transactional verification",
                "PHASE1_TEST",
            )
            found = fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM dbo.DimCategory WHERE CategoryID = ?",
                test_id,
            )
            if int(found) == 1:
                checks.append("transactional_insert_query=passed")
            else:
                failures.append("Transactional insert/query did not return one row")
        finally:
            connection.rollback()
    return VerificationResult(not failures, tuple(checks), tuple(failures))
