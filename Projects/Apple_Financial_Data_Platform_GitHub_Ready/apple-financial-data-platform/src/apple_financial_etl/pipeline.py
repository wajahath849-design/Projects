from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from .config import Settings
from .database import (
    create_database_engine,
    finish_etl_run,
    insert_quality_issues,
    start_etl_run,
    upsert_company,
    upsert_financial_facts,
    upsert_metrics,
)
from .sec_client import SecClient
from .transformer import transform_company_facts
from .validation import quality_summary, validate_financial_facts

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    fact_count: int
    issue_count: int
    error_count: int
    warning_count: int
    facts_csv: Path
    issues_csv: Path
    database_loaded: bool


def _save_outputs(
    settings: Settings, facts: pd.DataFrame, issues: pd.DataFrame
) -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    facts_path = settings.processed_data_dir / f"apple_financial_facts_{stamp}.csv"
    issues_path = settings.processed_data_dir / f"data_quality_issues_{stamp}.csv"
    facts.to_csv(facts_path, index=False)
    issues.to_csv(issues_path, index=False)
    return facts_path, issues_path


def run_pipeline(
    settings: Settings,
    history_years: int | None = None,
    force_refresh: bool = False,
    csv_only: bool = False,
) -> PipelineResult:
    run_id = uuid4()
    source_url = (
        f"https://data.sec.gov/api/xbrl/companyfacts/"
        f"CIK{settings.sec_cik.zfill(10)}.json"
    )
    client = SecClient(settings)
    payload = client.get_company_facts(force_refresh=force_refresh)
    facts = transform_company_facts(payload, history_years=history_years or settings.history_years)
    issues = validate_financial_facts(facts)
    summary = quality_summary(issues)
    facts_path, issues_path = _save_outputs(settings, facts, issues)

    if csv_only:
        LOGGER.info("CSV-only run completed; SQL Server was not used.")
        return PipelineResult(
            run_id=str(run_id),
            fact_count=len(facts),
            issue_count=len(issues),
            error_count=summary["errors"],
            warning_count=summary["warnings"],
            facts_csv=facts_path,
            issues_csv=issues_path,
            database_loaded=False,
        )

    engine = create_database_engine(settings)
    start_etl_run(engine, run_id, source_url)
    try:
        upsert_company(
            engine,
            cik=settings.sec_cik.zfill(10),
            company_name=payload.get("entityName", settings.sec_company_name),
            ticker=settings.sec_ticker,
        )
        upsert_metrics(engine, facts)
        loaded_count = upsert_financial_facts(engine, facts, run_id)
        insert_quality_issues(engine, issues, run_id)
        status = "FAILED_QUALITY" if summary["errors"] else "SUCCEEDED"
        finish_etl_run(
            engine,
            run_id,
            status=status,
            source_count=len(facts),
            loaded_count=loaded_count,
            error_count=summary["errors"],
            warning_count=summary["warnings"],
        )
    except Exception as exc:
        LOGGER.exception("ETL run failed")
        finish_etl_run(
            engine,
            run_id,
            status="FAILED",
            source_count=len(facts),
            loaded_count=0,
            error_count=summary["errors"] + 1,
            warning_count=summary["warnings"],
            message=str(exc)[:1000],
        )
        raise

    return PipelineResult(
        run_id=str(run_id),
        fact_count=len(facts),
        issue_count=len(issues),
        error_count=summary["errors"],
        warning_count=summary["warnings"],
        facts_csv=facts_path,
        issues_csv=issues_path,
        database_loaded=True,
    )
