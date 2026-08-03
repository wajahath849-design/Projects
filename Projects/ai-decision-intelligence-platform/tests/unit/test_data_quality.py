"""Unit tests for quality rules, gate semantics, and report output."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from decision_intelligence.quality.data_quality import DataQualityReport, QualityResult
from decision_intelligence.quality.quality_report import write_quality_reports
from decision_intelligence.quality.validation_rules import RULES


def _result(status: str = "PASS") -> QualityResult:
    return QualityResult(
        check_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        check_name="example",
        table_name="Example",
        category="VALIDITY",
        severity="CRITICAL",
        status=status,
        records_checked=10,
        failed_records=0 if status == "PASS" else 1,
        failure_percentage=0.0 if status == "PASS" else 10.0,
        description="Example check",
    )


def test_rule_catalog_covers_required_quality_categories() -> None:
    names = {rule.check_name for rule in RULES}
    assert len(RULES) >= 13
    assert "inventory_closing_stock_reconciliation" in names
    assert "negative_forecasts" in names
    assert "supplier_capacity_below_minimum_order" in names
    assert "warehouse_capacity_exceeded" in names


def test_critical_failure_closes_gate() -> None:
    report = DataQualityReport(uuid.uuid4(), datetime.now(UTC), (_result("FAIL"),))
    assert report.passed is False
    assert len(report.critical_failures) == 1


def test_report_writer_creates_json_csv_and_html(tmp_path: Path) -> None:
    report = DataQualityReport(uuid.uuid4(), datetime.now(UTC), (_result(),))
    paths = write_quality_reports(report, tmp_path)
    assert set(paths) == {"json", "csv", "html"}
    assert all(path.is_file() for path in paths.values())
    assert "DATA" not in paths["html"].read_text(encoding="utf-8")
