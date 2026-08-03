"""Execute SQL data-quality rules, persist outcomes, and enforce critical gates."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pyodbc

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.quality.validation_rules import RULES, ValidationRule
from decision_intelligence.settings import DatabaseSettings

LOGGER = logging.getLogger(__name__)


class DataQualityGateError(RuntimeError):
    """Raised when one or more critical quality checks fail."""


@dataclass(frozen=True)
class QualityResult:
    """Outcome of one validation rule."""

    check_id: uuid.UUID
    check_name: str
    table_name: str
    category: str
    severity: str
    status: str
    records_checked: int
    failed_records: int
    failure_percentage: float
    description: str


@dataclass(frozen=True)
class DataQualityReport:
    """Immutable results for one quality run."""

    pipeline_run_id: uuid.UUID
    created_at: datetime
    results: tuple[QualityResult, ...]

    @property
    def critical_failures(self) -> tuple[QualityResult, ...]:
        """Return critical failed checks that block downstream processing."""
        return tuple(
            result
            for result in self.results
            if result.severity == "CRITICAL" and result.status == "FAIL"
        )

    @property
    def passed(self) -> bool:
        """Return true only when the critical gate is clear."""
        return not self.critical_failures


def _evaluate_rule(connection: pyodbc.Connection, rule: ValidationRule) -> QualityResult:
    records_checked = int(fetch_scalar(connection, rule.records_sql) or 0)
    failed_records = int(fetch_scalar(connection, rule.failures_sql) or 0)
    if failed_records < 0 or records_checked < 0 or failed_records > records_checked:
        raise RuntimeError(f"Rule {rule.check_name} returned invalid counts")
    status = "PASS" if failed_records == 0 else "FAIL" if rule.severity == "CRITICAL" else "WARNING"
    percentage = 0.0 if records_checked == 0 else 100.0 * failed_records / records_checked
    return QualityResult(
        check_id=uuid.uuid4(),
        check_name=rule.check_name,
        table_name=rule.table_name,
        category=rule.category,
        severity=rule.severity,
        status=status,
        records_checked=records_checked,
        failed_records=failed_records,
        failure_percentage=percentage,
        description=rule.description,
    )


def _persist_results(
    connection: pyodbc.Connection,
    report: DataQualityReport,
    check_date_key: int,
) -> None:
    rows = [
        (
            result.check_id,
            check_date_key,
            result.table_name,
            result.check_name,
            result.category,
            result.severity,
            result.status,
            result.records_checked,
            result.failed_records,
            result.failure_percentage,
            json.dumps({"description": result.description}, sort_keys=True),
            report.pipeline_run_id,
            "DATA_QUALITY_FRAMEWORK",
            "phase-4-v1",
        )
        for result in report.results
    ]
    connection.cursor().executemany(
        """INSERT dbo.FactDataQuality
        (CheckID,CheckDateKey,TableName,CheckName,CheckCategory,Severity,Status,
         RecordsChecked,FailedRecords,FailurePercentage,DetailsJson,PipelineRunID,
         SourceSystem,DataVersion)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )


def _ensure_check_date(connection: pyodbc.Connection, value: date) -> int:
    """Ensure the actual quality-run date exists in DimDate and return its key."""
    date_key = value.year * 10000 + value.month * 100 + value.day
    connection.execute(
        """IF NOT EXISTS (SELECT 1 FROM dbo.DimDate WHERE DateKey=?)
        INSERT dbo.DimDate
        (DateKey,FullDate,DayOfWeek,DayName,WeekOfYear,MonthNumber,MonthName,
         QuarterNumber,CalendarYear,IsWeekend,SourceSystem,DataVersion)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        date_key,
        date_key,
        value,
        value.isoweekday(),
        value.strftime("%A"),
        value.isocalendar().week,
        value.month,
        value.strftime("%B"),
        (value.month - 1) // 3 + 1,
        value.year,
        int(value.weekday() >= 5),
        "DATA_QUALITY_FRAMEWORK",
        "phase-4-v1",
    )
    return date_key


def run_data_quality(settings: DatabaseSettings) -> DataQualityReport:
    """Run all configured checks transactionally and persist their outcomes."""
    pipeline_run_id = uuid.uuid4()
    with connect(settings) as connection:
        try:
            results = tuple(_evaluate_rule(connection, rule) for rule in RULES)
            created_at = datetime.now(UTC)
            report = DataQualityReport(
                pipeline_run_id=pipeline_run_id,
                created_at=created_at,
                results=results,
            )
            check_date_key = _ensure_check_date(connection, created_at.date())
            _persist_results(connection, report, check_date_key)
            connection.commit()
        except Exception:
            connection.rollback()
            LOGGER.exception("Data-quality run %s failed", pipeline_run_id)
            raise
    return report


def assert_latest_quality_gate(settings: DatabaseSettings) -> None:
    """Block downstream processing if the latest persisted run has critical failures."""
    with connect(settings) as connection:
        run_id = fetch_scalar(
            connection,
            """SELECT TOP 1 PipelineRunID FROM dbo.FactDataQuality
            WHERE PipelineRunID IS NOT NULL ORDER BY DataQualityKey DESC""",
        )
        failures = int(
            fetch_scalar(
                connection,
                """SELECT COUNT(*) FROM dbo.FactDataQuality
                WHERE PipelineRunID=? AND Severity='CRITICAL' AND Status='FAIL'""",
                run_id,
            )
        )
    if failures:
        raise DataQualityGateError(
            f"Latest data-quality run {run_id} has {failures} critical failure(s)"
        )
