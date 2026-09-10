"""Evaluate incident investigation against private truth without exposing truth to production."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.incident_engine import RootCauseInvestigationEngine
from src.incident_similarity import IncidentSimilarityEngine


TRUTH_PATH = ROOT / "evaluation/private/root_cause_truth.json"
RESULT_PATH = ROOT / "evaluation/results/root_cause_phase31.json"


def evaluate_case(case: dict, investigation_engine, similarity_engine) -> dict:
    # Only the incident identifier crosses into production logic. Expected answers stay here.
    investigation = investigation_engine.investigate(case["incident_id"])
    matches = similarity_engine.retrieve(case["incident_id"], top_k=5)
    observed_codes = {
        item["details"].get("event_code")
        for item in investigation.evidence["logs"]
    }
    checks_text = " ".join(investigation.recommended_checks).lower()
    component_text = investigation.likely_area.lower()
    evaluations = {
        "incident_detection": investigation.incident_id == case["incident_id"],
        "component_identification": all(
            component.lower() in component_text for component in case["expected_components"]
        ),
        "evidence_retrieval": set(case["required_log_codes"]) <= observed_codes,
        "similar_incident_retrieval": any(
            item.incident.root_cause == case["expected_similar_root_cause"]
            for item in matches
        ),
        "root_cause_category": (
            investigation.recorded_root_cause == case["expected_root_cause"]
        ),
        "recommendation_relevance": all(
            term.lower() in checks_text for term in case["recommendation_terms"]
        ),
    }
    return {
        "case_id": case["case_id"],
        "synthetic_scenario": case["synthetic_scenario"],
        "incident_id": case["incident_id"],
        "observed_root_cause": investigation.recorded_root_cause,
        "observed_likely_area": investigation.likely_area,
        "observed_log_codes": sorted(code for code in observed_codes if code),
        "top_similar_incidents": [
            {
                "incident_id": item.incident.incident_id,
                "root_cause": item.incident.root_cause,
                "similarity": item.similarity,
            }
            for item in matches
        ],
        "checks": evaluations,
        "passed": all(evaluations.values()),
    }


def run_evaluation(
    truth_path: Path = TRUTH_PATH,
    result_path: Path = RESULT_PATH,
) -> dict:
    # Construct production engines before the evaluator opens private truth.
    investigation_engine = RootCauseInvestigationEngine(ROOT / "database/datacenter.db", ROOT)
    similarity_engine = IncidentSimilarityEngine(ROOT / "database/datacenter.db")
    private_truth = json.loads(truth_path.read_text(encoding="utf-8"))
    cases = [
        evaluate_case(case, investigation_engine, similarity_engine)
        for case in private_truth["cases"]
    ]
    metric_names = tuple(cases[0]["checks"]) if cases else ()
    metrics = {
        name: {
            "passed": sum(case["checks"][name] for case in cases),
            "total": len(cases),
            "accuracy": (
                round(sum(case["checks"][name] for case in cases) / len(cases), 4)
                if cases else None
            ),
        }
        for name in metric_names
    }
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "six protected deterministic synthetic root-cause scenarios",
        "truth_isolation": (
            "Truth is loaded only by this evaluation runner and is never passed to the "
            "investigation or retrieval engines."
        ),
        "case_count": len(cases),
        "passed_cases": sum(case["passed"] for case in cases),
        "metrics": metrics,
        "cases": cases,
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    report = run_evaluation()
    print(json.dumps({
        "case_count": report["case_count"],
        "passed_cases": report["passed_cases"],
        "metrics": report["metrics"],
    }, indent=2))


if __name__ == "__main__":
    main()
