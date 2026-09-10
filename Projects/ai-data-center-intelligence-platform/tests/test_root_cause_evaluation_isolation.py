import json
from pathlib import Path

from evaluation.evaluate_root_cause import TRUTH_PATH, run_evaluation
from src.semantic_layer import SemanticLayer


ROOT = Path(__file__).resolve().parents[1]


def test_private_truth_covers_six_requested_scenarios() -> None:
    payload = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    scenarios = {case["synthetic_scenario"] for case in payload["cases"]}
    assert scenarios == {
        "Cooling failure", "Network outage", "Power disturbance",
        "Disk degradation", "Server overheating", "Application overload",
    }


def test_production_source_does_not_reference_evaluation_truth() -> None:
    for path in (ROOT / "src").glob("*.py"):
        assert "evaluation/private" not in path.read_text(encoding="utf-8").lower()
    chunks = SemanticLayer(ROOT).build_chunks()
    assert chunks
    assert all("evaluation" not in str(chunk.metadata).lower() for chunk in chunks)


def test_protected_root_cause_evaluation_passes(tmp_path) -> None:
    report = run_evaluation(result_path=tmp_path / "root_cause.json")
    assert report["case_count"] == 6
    assert report["passed_cases"] == 6
    assert all(metric["accuracy"] == 1.0 for metric in report["metrics"].values())
