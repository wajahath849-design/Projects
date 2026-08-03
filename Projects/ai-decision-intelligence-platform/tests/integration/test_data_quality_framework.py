"""Live SQL Server tests for persisted Phase 4 quality outcomes."""

from pathlib import Path

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.quality.data_quality import assert_latest_quality_gate
from decision_intelligence.quality.validation_rules import RULES
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_latest_quality_run_is_complete_and_passed() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        run_id = fetch_scalar(
            connection,
            "SELECT TOP 1 PipelineRunID FROM dbo.FactDataQuality ORDER BY DataQualityKey DESC",
        )
        total = fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactDataQuality WHERE PipelineRunID=?",
            run_id,
        )
        failures = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactDataQuality
            WHERE PipelineRunID=? AND Severity='CRITICAL' AND Status='FAIL'""",
            run_id,
        )
    assert int(total) == len(RULES)
    assert int(failures) == 0


def test_latest_quality_gate_allows_downstream_processing() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    assert_latest_quality_gate(settings)


def test_quality_results_have_valid_counts_and_details() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        invalid = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactDataQuality
            WHERE SourceSystem='DATA_QUALITY_FRAMEWORK'
              AND (RecordsChecked<0 OR FailedRecords<0 OR FailedRecords>RecordsChecked
                OR DetailsJson IS NULL OR ISJSON(DetailsJson)<>1)""",
        )
    assert int(invalid) == 0
