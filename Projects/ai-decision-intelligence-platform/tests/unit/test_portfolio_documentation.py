"""Phase 17 documentation completeness and honesty checks."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_required_portfolio_documents_exist_and_are_nonempty() -> None:
    required = (
        "architecture.md", "model_card.md", "data_dictionary.md", "api.md",
        "installation.md", "power_bi_guide.md", "interview_guide.md",
        "cv_description.md", "release_checklist.md",
    )
    for name in required:
        path = PROJECT_ROOT / "docs" / name
        assert path.is_file()
        assert len(path.read_text(encoding="utf-8")) > 200


def test_readme_contains_honest_scope_and_core_guides() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "not represented as production-ready" in readme
    assert "does not claim" in readme
    assert "synthetic" in readme.lower()
    assert "verify_project.py" in readme
    assert "Architecture" in readme and "Power BI guide" in readme
