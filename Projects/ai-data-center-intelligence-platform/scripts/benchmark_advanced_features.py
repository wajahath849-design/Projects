"""Measure Phase L streaming, investigation, and analytical performance."""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.impact.engine import ImpactAnalysisEngine
from src.investigation.service import MultiAgentInvestigationService
from src.realtime.configuration import RealtimeConfig
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.sustainability.engine import CostCarbonEngine


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "evaluation/results/advanced_performance_phase_l.json"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return round(ordered[index], 3)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def timed(function, *args, **kwargs):
    started = time.perf_counter_ns()
    value = function(*args, **kwargs)
    return value, (time.perf_counter_ns() - started) / 1_000_000


def run_benchmark(result_path: Path = RESULT) -> dict[str, object]:
    canonical = ROOT / "database/datacenter.db"
    before = digest(canonical)
    with tempfile.TemporaryDirectory(
        prefix="ai-dc-stream-benchmark-", ignore_cleanup_errors=True
    ) as temporary:
        store = RealtimeStore(
            Path(temporary) / "realtime.db", canonical,
            ROOT / "database/realtime_schema.sql",
        )
        store.initialize()
        session = store.create_session(simulation_session_id="SIM-PERFORMANCE-L")
        config = RealtimeConfig.from_yaml(ROOT / "config/realtime.yaml")
        simulator = TelemetrySimulator(
            canonical, random_seed=2026,
            tick_interval_seconds=config.tick_interval_seconds,
            server_sample_size_per_facility=0,
        )
        analytics = StreamingAnalyticsService(
            store, config, ROOT / "analytics/live_health_weights.yaml"
        )
        start = datetime(2026, 5, 1, tzinfo=timezone.utc)
        process_ms: list[float] = []
        events = 0
        anomalies = 0
        wall_started = time.perf_counter_ns()
        for tick in range(10):
            batch = simulator.generate_tick(
                session, start + timedelta(seconds=tick * config.tick_interval_seconds)
            )
            result, elapsed = timed(analytics.process, batch)
            process_ms.append(elapsed)
            events += result.ingestion.total_inserted
            anomalies += len(result.anomalies)
        wall_seconds = (time.perf_counter_ns() - wall_started) / 1_000_000_000
        query_ms = [
            timed(analytics.current_status, session, "DC-FRA-01")[1]
            for _ in range(50)
        ]
        simple_session = store.create_session(simulation_session_id="SIM-SIMPLE-L")
        for tick in range(2):
            analytics.process(simulator.generate_tick(
                simple_session,
                start + timedelta(hours=1, seconds=tick * config.tick_interval_seconds),
            ))
        investigator = MultiAgentInvestigationService(store, canonical)
        simple_ms = [
            timed(investigator.investigate, simple_session, "DC-FRA-01")[1]
            for _ in range(10)
        ]
        simple_route = investigator.route(simple_session, "DC-FRA-01")

    sustainability = CostCarbonEngine(
        canonical,
        ROOT / "data/assumptions/energy_prices.csv",
        ROOT / "data/assumptions/carbon_intensity.csv",
        ROOT / "analytics/efficiency_opportunity_weights.yaml",
    )
    _, cost_ms = timed(
        sustainability.summarize, "2025-01-01", "2025-12-31"
    )
    impact = ImpactAnalysisEngine(canonical, sustainability)
    _, impact_ms = timed(
        impact.correlation, "pue", "cooling_power_kw",
        facility_id="DC-FRA-01", start_date="2024-01-01", end_date="2025-12-31",
    )

    simulation_eval = json.loads(
        (ROOT / "evaluation/results/advanced_simulation_phase_l.json").read_text(
            encoding="utf-8"
        )
    )
    multi = [
        float(case["investigation_ms"]) for case in simulation_eval["cases"]
        if case["route"] == "multi_agent"
    ]
    inherited = json.loads(
        (ROOT / "evaluation/results/performance_phase34_offline.json").read_text(
            encoding="utf-8"
        )
    )["summary"]
    report = {
        "scope": "local synthetic Phase L benchmark",
        "historical_database_unchanged": digest(canonical) == before,
        "streaming": {
            "events_processed": events,
            "elapsed_seconds": round(wall_seconds, 3),
            "events_per_second": round(events / wall_seconds, 3),
            "process_p50_ms": percentile(process_ms, 0.50),
            "process_p95_ms": percentile(process_ms, 0.95),
            "anomalies_detected": anomalies,
            "current_query_p50_ms": percentile(query_ms, 0.50),
            "current_query_p95_ms": percentile(query_ms, 0.95),
        },
        "investigation": {
            "single_route_cases": 10,
            "single_route": simple_route,
            "single_p50_ms": percentile(simple_ms, 0.50),
            "single_p95_ms": percentile(simple_ms, 0.95),
            "multi_agent_cases": len(multi),
            "multi_p50_ms": percentile(multi, 0.50) if multi else None,
            "multi_p95_ms": percentile(multi, 0.95) if multi else None,
            "note": "Multi-agent routing is reserved for complex or high-severity evidence.",
        },
        "analytics": {
            "cost_carbon_2025_ms": round(cost_ms, 3),
            "impact_correlation_2y_ms": round(impact_ms, 3),
        },
        "existing_pipeline": {
            "total_response_p50_ms": inherited["total_latency"]["p50_ms"],
            "database_p95_ms": inherited["database_latency"]["p95_ms"],
            "rag_p95_ms": inherited["stages"]["rag_retrieval_ms"]["p95_ms"],
            "chart_p95_ms": inherited["stages"]["chart_generation_ms"]["p95_ms"],
            "sql_generation_p95_ms": inherited["stages"]["llm_sql_generation_ms"]["p95_ms"],
        },
        "ollama_inference": {
            "measured_ms": None,
            "status": "not measured in offline Phase L audit",
            "reason": "Hardware/model-dependent local inference is not required for deterministic feature correctness.",
        },
    }
    report["performance_regression_status"] = {
        "passed": (
            report["historical_database_unchanged"]
            and report["streaming"]["events_per_second"] > 10
            and report["streaming"]["current_query_p95_ms"] < 250
            and report["analytics"]["impact_correlation_2y_ms"] < 5_000
        ),
        "thresholds": {
            "stream_events_per_second_min": 10,
            "current_query_p95_ms_max": 250,
            "impact_correlation_ms_max": 5_000,
        },
    }
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2))
