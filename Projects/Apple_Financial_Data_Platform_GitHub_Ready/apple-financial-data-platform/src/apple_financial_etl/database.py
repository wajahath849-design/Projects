from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Iterable
from uuid import UUID

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import Settings

LOGGER = logging.getLogger(__name__)


def create_master_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_master_url,
        pool_pre_ping=True,
        future=True,
        isolation_level="AUTOCOMMIT",
    )


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        future=True,
        fast_executemany=True,
    )


def _wait_for_engine(engine: Engine, attempts: int = 20, delay_seconds: int = 2) -> None:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("SELECT 1")
            return
        except Exception as exc:  # Driver-specific connection exceptions vary.
            last_error = exc
            if attempt == attempts:
                break
            LOGGER.info(
                "Waiting for SQL Server (%s/%s): %s",
                attempt,
                attempts,
                exc,
            )
            time.sleep(delay_seconds)
    raise RuntimeError(f"SQL Server connection failed after retries: {last_error}")


def _split_sql_batches(script: str) -> Iterable[str]:
    batches = re.split(r"^\s*GO\s*$", script, flags=re.I | re.M)
    return [batch.strip() for batch in batches if batch.strip()]


def initialize_database(settings: Settings, sql_dir: Path) -> None:
    database_name = settings.mssql_database.replace("]", "]]")
    database_literal = settings.mssql_database.replace("'", "''")
    master_engine = create_master_engine(settings)
    _wait_for_engine(master_engine)
    with master_engine.connect() as connection:
        connection.exec_driver_sql(
            f"IF DB_ID(N'{database_literal}') IS NULL "
            f"BEGIN CREATE DATABASE [{database_name}] END"
        )

    engine = create_database_engine(settings)
    _wait_for_engine(engine)
    for sql_file in sorted(sql_dir.glob("*.sql")):
        LOGGER.info("Applying SQL script %s", sql_file)
        script = sql_file.read_text(encoding="utf-8")
        with engine.begin() as connection:
            for batch in _split_sql_batches(script):
                connection.exec_driver_sql(batch)


def start_etl_run(engine: Engine, run_id: UUID, source_url: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit.ETLRun
                    (RunId, PipelineName, SourceSystem, SourceUrl, Status, StartedAtUtc)
                VALUES
                    (:run_id, 'apple-financial-etl', 'SEC EDGAR Company Facts', :source_url,
                     'RUNNING', SYSUTCDATETIME())
                """
            ),
            {"run_id": str(run_id), "source_url": source_url},
        )


def finish_etl_run(
    engine: Engine,
    run_id: UUID,
    status: str,
    source_count: int,
    loaded_count: int,
    error_count: int,
    warning_count: int,
    message: str | None = None,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE audit.ETLRun
                SET Status = :status,
                    SourceRecordCount = :source_count,
                    LoadedRecordCount = :loaded_count,
                    ErrorCount = :error_count,
                    WarningCount = :warning_count,
                    Message = :message,
                    FinishedAtUtc = SYSUTCDATETIME()
                WHERE RunId = :run_id
                """
            ),
            {
                "run_id": str(run_id),
                "status": status,
                "source_count": source_count,
                "loaded_count": loaded_count,
                "error_count": error_count,
                "warning_count": warning_count,
                "message": message,
            },
        )


def _records_for_sql(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    clean = df.where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def upsert_company(engine: Engine, cik: str, company_name: str, ticker: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                MERGE finance.Company AS target
                USING (SELECT :cik AS CIK) AS source
                ON target.CIK = source.CIK
                WHEN MATCHED THEN
                    UPDATE SET CompanyName = :company_name, Ticker = :ticker,
                               UpdatedAtUtc = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (CIK, CompanyName, Ticker)
                    VALUES (:cik, :company_name, :ticker);
                """
            ),
            {"cik": cik, "company_name": company_name, "ticker": ticker},
        )


def upsert_metrics(engine: Engine, facts: pd.DataFrame) -> None:
    metrics = facts[
        ["metric_code", "metric_name", "statement_name", "category_name", "unit"]
    ].drop_duplicates()
    sql = text(
        """
        MERGE finance.Metric AS target
        USING (SELECT :metric_code AS MetricCode) AS source
        ON target.MetricCode = source.MetricCode
        WHEN MATCHED THEN
            UPDATE SET MetricName = :metric_name, StatementName = :statement_name,
                       CategoryName = :category_name, DefaultUnit = :unit,
                       UpdatedAtUtc = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (MetricCode, MetricName, StatementName, CategoryName, DefaultUnit)
            VALUES (:metric_code, :metric_name, :statement_name, :category_name, :unit);
        """
    )
    with engine.begin() as connection:
        for record in _records_for_sql(metrics):
            connection.execute(sql, record)


def upsert_financial_facts(engine: Engine, facts: pd.DataFrame, run_id: UUID) -> int:
    if facts.empty:
        return 0

    stage = facts.copy()
    stage["run_id"] = str(run_id)
    stage.to_sql(
        "FinancialFactStage",
        engine,
        schema="stage",
        if_exists="append",
        index=False,
        chunksize=500,
    )

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                MERGE finance.FinancialFact AS target
                USING (
                    SELECT
                        s.business_key,
                        c.CompanyId,
                        m.MetricId,
                        s.taxonomy,
                        s.source_tag,
                        s.unit,
                        s.value,
                        s.period_start,
                        s.period_end,
                        s.duration_days,
                        s.period_type,
                        s.fiscal_year,
                        s.fiscal_period,
                        s.form_type,
                        s.filed_date,
                        s.accession_number,
                        s.source_url,
                        s.is_derived,
                        s.derivation_method,
                        s.run_id
                    FROM stage.FinancialFactStage s
                    INNER JOIN finance.Company c ON c.CIK = s.company_cik
                    INNER JOIN finance.Metric m ON m.MetricCode = s.metric_code
                    WHERE s.run_id = :run_id
                ) AS source
                ON target.BusinessKey = source.business_key
                WHEN MATCHED THEN
                    UPDATE SET
                        CompanyId = source.CompanyId,
                        MetricId = source.MetricId,
                        Taxonomy = source.taxonomy,
                        SourceTag = source.source_tag,
                        Unit = source.unit,
                        FactValue = source.value,
                        PeriodStart = source.period_start,
                        PeriodEnd = source.period_end,
                        DurationDays = source.duration_days,
                        PeriodType = source.period_type,
                        FiscalYear = source.fiscal_year,
                        FiscalPeriod = source.fiscal_period,
                        FormType = source.form_type,
                        FiledDate = source.filed_date,
                        AccessionNumber = source.accession_number,
                        SourceUrl = source.source_url,
                        IsDerived = source.is_derived,
                        DerivationMethod = source.derivation_method,
                        LastRunId = source.run_id,
                        UpdatedAtUtc = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (
                        BusinessKey, CompanyId, MetricId, Taxonomy, SourceTag, Unit, FactValue,
                        PeriodStart, PeriodEnd, DurationDays, PeriodType, FiscalYear, FiscalPeriod,
                        FormType, FiledDate, AccessionNumber, SourceUrl, IsDerived,
                        DerivationMethod, LastRunId
                    )
                    VALUES (
                        source.business_key, source.CompanyId, source.MetricId, source.taxonomy,
                        source.source_tag, source.unit, source.value, source.period_start,
                        source.period_end, source.duration_days, source.period_type,
                        source.fiscal_year, source.fiscal_period, source.form_type,
                        source.filed_date, source.accession_number, source.source_url,
                        source.is_derived, source.derivation_method, source.run_id
                    );

                DELETE FROM stage.FinancialFactStage WHERE run_id = :run_id;
                """
            ),
            {"run_id": str(run_id)},
        )
    return int(len(facts))


def insert_quality_issues(engine: Engine, issues: pd.DataFrame, run_id: UUID) -> int:
    if issues.empty:
        return 0
    records = _records_for_sql(issues)
    sql = text(
        """
        INSERT INTO audit.DataQualityIssue
            (RunId, Severity, CheckName, MetricCode, FiscalYear, FiscalPeriod,
             PeriodEnd, IssueDetails, DetectedAtUtc)
        VALUES
            (:run_id, :severity, :check_name, :metric_code, :fiscal_year, :fiscal_period,
             :period_end, :issue_details, :detected_at_utc)
        """
    )
    with engine.begin() as connection:
        for record in records:
            record["run_id"] = str(run_id)
            connection.execute(sql, record)
    return len(records)


def query_to_csv(engine: Engine, query: str, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as connection:
        df = pd.read_sql_query(text(query), connection)
    df.to_csv(destination, index=False)
    return len(df)
