from pathlib import Path

from scripts.validate_cost_carbon import run_validation


ROOT = Path(__file__).resolve().parents[1]


def test_cost_carbon_independent_validation_passes(tmp_path: Path) -> None:
    report = run_validation(tmp_path / "cost-carbon.json")
    assert report["all_passed"]
    assert len(report["metrics"]) == 4
    assert len(report["checks"]) == 8


def test_advanced_truth_never_enters_production_source() -> None:
    for path in (ROOT / "src").rglob("*.py"):
        source = path.read_text(encoding="utf-8").lower()
        assert "advanced_simulation_truth" not in source
        assert "evaluation/private" not in source
