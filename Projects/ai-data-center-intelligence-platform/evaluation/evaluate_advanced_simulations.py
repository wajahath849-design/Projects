"""Protected evaluation for the six observable incident simulations."""

from __future__ import annotations

import json
import gc
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from src.investigation.service import MultiAgentInvestigationService
from src.realtime.configuration import RealtimeConfig
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.simulation.lab import IncidentSimulationLab


ROOT = Path(__file__).resolve().parents[1]
TRUTH_PATH = ROOT / "evaluation/private/advanced_simulation_truth.json"
RESULT_PATH = ROOT / "evaluation/results/advanced_simulation_phase_l.json"


def _production_runtime(database_path: Path, seed: int) -> tuple[IncidentSimulationLab, MultiAgentInvestigationService]:
    store = RealtimeStore(
        database_path, ROOT / "database/datacenter.db", ROOT / "database/realtime_schema.sql"
    )
    store.initialize()
    config = RealtimeConfig.from_yaml(ROOT / "config/realtime.yaml")
    simulator = TelemetrySimulator(
        ROOT / "database/datacenter.db", random_seed=seed,
        tick_interval_seconds=config.tick_interval_seconds,
        server_sample_size_per_facility=1,
    )
    analytics = StreamingAnalyticsService(
        store, config, ROOT / "analytics/live_health_weights.yaml"
    )
    return (
        IncidentSimulationLab(
            store, simulator, analytics, ROOT / "config/simulation_scenarios.yaml"
        ),
        MultiAgentInvestigationService(store, ROOT / "database/datacenter.db"),
    )


def _observed_domain(text: str, domains: list[str]) -> str | None:
    lowered = text.lower()
    return next((domain for domain in domains if domain.lower() in lowered), None)


def run_evaluation(
    truth_path: Path = TRUTH_PATH,
    result_path: Path = RESULT_PATH,
) -> dict[str, object]:
    # Production objects never receive truth fields. The evaluator passes only
    # scenario/facility/session identifiers, then compares returned evidence.
    private = json.loads(truth_path.read_text(encoding="utf-8"))
    cases: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix="ai-dc-advanced-eval-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        for index, expected in enumerate(private["cases"]):
            lab, investigation = _production_runtime(
                temporary_root / f"case-{index}.db", seed=900 + index
            )
            session_id = lab.start(
                expected["scenario_key"], facility_id="DC-FRA-01",
                simulation_session_id=f"SIM-ADV-EVAL-{index:02d}",
                started_at=datetime(2026, 4, index + 1, tzinfo=timezone.utc),
            )
            simulation_started = time.perf_counter_ns()
            steps = lab.run_to_completion(session_id)
            simulation_ms = (time.perf_counter_ns() - simulation_started) / 1_000_000
            investigation_started = time.perf_counter_ns()
            report = investigation.investigate(session_id, "DC-FRA-01")
            investigation_ms = (time.perf_counter_ns() - investigation_started) / 1_000_000
            evidence_ids = {item.evidence_id for item in report.evidence_timeline}
            expected_domains = list(expected["expected_domains"])
            observed_domain = _observed_domain(report.likely_contributor, expected_domains)
            first_signal = (
                report.first_abnormal_signal.get("metric_or_event")
                if report.first_abnormal_signal else None
            )
            expected_signals = set(expected["expected_first_signals"])
            observed_metrics = {item.metric_or_event for item in report.evidence_timeline}
            checks = {
                "root_cause_area": observed_domain is not None,
                "first_abnormal_signal": first_signal in expected_signals,
                "relevant_evidence_retrieval": bool(observed_metrics & expected_signals),
                "claim_grounding": report.verified and all(
                    set(ids) <= evidence_ids for ids in report.claim_evidence_ids.values()
                ),
                "no_unsupported_certainty": (
                    report.confidence_label != "CONFIRMED"
                    and "definitely" not in report.incident_summary.lower()
                    and "caused" not in report.incident_summary.lower()
                ),
                "alternative_hypotheses": (
                    bool(report.alternative_explanations)
                    if expected["requires_alternative_hypothesis"] else True
                ),
                "truth_isolation": "evaluation/private" not in str(report.to_dict()).lower(),
            }
            cases.append({
                "case_id": expected["case_id"],
                "scenario_key": expected["scenario_key"],
                "route": report.route,
                "agents_invoked": list(report.invoked_agents),
                "observed_likely_contributor": report.likely_contributor,
                "observed_first_signal": first_signal,
                "evidence_count": len(report.evidence_timeline),
                "simulation_events_processed": sum(
                    step.analytics.ingestion.total_inserted for step in steps
                ),
                "simulation_ms": round(simulation_ms, 3),
                "investigation_ms": round(investigation_ms, 3),
                "checks": checks,
                "passed": all(checks.values()),
            })
            del lab, investigation, report
            gc.collect()
    metric_names = list(cases[0]["checks"]) if cases else []
    metrics = {
        name: {
            "passed": sum(bool(case["checks"][name]) for case in cases),
            "total": len(cases),
        }
        for name in metric_names
    }
    report = {
        "scope": "six protected deterministic streaming incident scenarios",
        "truth_isolation": (
            "Expected domains are loaded only by this evaluator and are never passed "
            "to the simulator, specialists, synthesizer, or evidence verifier."
        ),
        "case_count": len(cases),
        "passed_cases": sum(bool(case["passed"]) for case in cases),
        "total_events_processed": sum(int(case["simulation_events_processed"]) for case in cases),
        "metrics": metrics,
        "cases": cases,
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run_evaluation()
    print(json.dumps({
        "passed_cases": result["passed_cases"],
        "case_count": result["case_count"],
        "total_events_processed": result["total_events_processed"],
        "metrics": result["metrics"],
    }, indent=2))
