"""Static validation for the Power BI construction package."""

from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_theme_and_dax_package_are_complete() -> None:
    theme = json.loads((
        PROJECT_ROOT / "powerbi" / "theme" / "decision_intelligence_theme.json"
    ).read_text(encoding="utf-8"))
    assert theme["name"] == "Decision Intelligence"
    dax = (PROJECT_ROOT / "powerbi" / "dax" / "measures.dax").read_text(encoding="utf-8")
    assert len(re.findall(r"(?m)^[A-Za-z][A-Za-z ]+\s*=\s*$", dax)) >= 31
    for required in (
        "WAPE", "Forecast Accuracy", "Stockout", "Scenario Profit Impact",
        "Data Quality Pass Rate",
    ):
        assert required in dax


def test_seven_pages_and_no_pbix_claim() -> None:
    pages = (PROJECT_ROOT / "powerbi" / "docs" / "page_layouts.md").read_text(
        encoding="utf-8"
    )
    assert len(re.findall(r"(?m)^## Page [1-7]", pages)) == 7
    checklist = (PROJECT_ROOT / "powerbi" / "tests" / "power_bi_checklist.md").read_text(
        encoding="utf-8"
    )
    assert "No screenshot or PBIX claim" in checklist
