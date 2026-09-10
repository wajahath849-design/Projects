import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.impact.engine import ImpactAnalysisEngine
from src.investigation.evidence import EvidenceRecord, deduplicate_evidence
from src.investigation.service import EvidenceVerifier, MultiAgentInvestigationService
from src.realtime.configuration import RealtimeConfig
from src.realtime.models import TelemetryBatch, TelemetryEvent
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.simulation.lab import IncidentSimulationLab
from src.sustainability.engine import CostCarbonEngine


ROOT = Path(__file__).resolve().parents[1]


def build_completed_scenario(tmp_path: Path) -> tuple[RealtimeStore, str]:
    store = RealtimeStore(
        tmp_path / "realtime.db",
        ROOT / "database/datacenter.db",
        ROOT / "database/realtime_schema.sql",
    )
    store.initialize()
    config = RealtimeConfig.from_yaml(ROOT / "config/realtime.yaml")
    simulator = TelemetrySimulator(
        ROOT / "database/datacenter.db", random_seed=71,
        tick_interval_seconds=config.tick_interval_seconds,
        server_sample_size_per_facility=1,
    )
    service = StreamingAnalyticsService(
        store, config, ROOT / "analytics/live_health_weights.yaml"
    )
    lab = IncidentSimulationLab(
        store, simulator, service, ROOT / "config/simulation_scenarios.yaml"
    )
    session = lab.start(
        "cascading_failure", facility_id="DC-FRA-01",
        simulation_session_id="SIM-FAILURE-MODES",
        started_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    lab.run_to_completion(session)
    return store, session


def test_agent_and_ollama_failures_degrade_to_verified_partial_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, session = build_completed_scenario(tmp_path)
    service = MultiAgentInvestigationService(store, ROOT / "database/datacenter.db")

    def failed_historical(*_args, **_kwargs):
        raise sqlite3.OperationalError("synthetic specialist outage")

    monkeypatch.setattr(service, "_historical_analyst", failed_historical)
    report = service.investigate(session, "DC-FRA-01")
    assert "historical_analyst" in report.partial_failures
    assert report.confidence_label in {"POSSIBLE", "INSUFFICIENT_EVIDENCE"}
    assert all(
        set(ids) <= {row.evidence_id for row in report.evidence_timeline}
        for ids in report.claim_evidence_ids.values()
    )

    def timed_out_synthesizer(_payload):
        raise TimeoutError("local model unavailable")

    fallback = MultiAgentInvestigationService(
        store, ROOT / "database/datacenter.db", synthesizer=timed_out_synthesizer
    ).investigate(session, "DC-FRA-01")
    assert "root_cause_synthesizer" in fallback.partial_failures
    assert "observable evidence records" in fallback.incident_summary


def test_unsupported_model_wording_is_rejected() -> None:
    record = EvidenceRecord(
        "E-1", "metric_change", "test", "2026-01-01T00:00:00+00:00",
        "DC-FRA-01", None, "pue", {"value": 1.8}, "high", "test", "metric_analyst",
    )
    verifier = EvidenceVerifier()
    assert verifier.verify((record,), {
        "summary": ("E-1",), "first_signal": ("E-1",),
        "likely_contributor": ("MISSING",),
    }) is False
    deduplicated = deduplicate_evidence((record, record))
    assert deduplicated == (record,)


def test_sessions_are_isolated_and_support_concurrent_reads(tmp_path: Path) -> None:
    store = RealtimeStore(
        tmp_path / "realtime.db", ROOT / "database/datacenter.db",
        ROOT / "database/realtime_schema.sql",
    )
    store.initialize()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    sessions = [store.create_session(simulation_session_id=f"SIM-ISO-{index}") for index in range(2)]
    for index, session in enumerate(sessions):
        event = TelemetryEvent.create(
            event_id=f"RTM-ISO-{index}", event_timestamp=timestamp,
            ingestion_timestamp=timestamp, facility_id="DC-FRA-01",
            metric_name="pue", metric_value=1.4 + index / 10,
            unit="ratio", source="test", simulation_session_id=session,
        )
        store.ingest_batch(TelemetryBatch(metrics=(event,)))
    assert [len(store.current_metric_rows(session)) for session in sessions] == [0, 0]
    with store.read_connection() as connection:
        counts = [connection.execute(
            "SELECT COUNT(*) FROM realtime_metric_events WHERE simulation_session_id=?",
            (session,),
        ).fetchone()[0] for session in sessions]
    assert counts == [1, 1]
    with ThreadPoolExecutor(max_workers=4) as executor:
        versions = list(executor.map(store.session_versions, sessions * 8))
    assert versions == [(1, 0)] * 16


def test_missing_cost_assumption_and_insufficient_impact_samples_fail_safely(
    tmp_path: Path,
) -> None:
    prices = pd.read_csv(ROOT / "data/assumptions/energy_prices.csv")
    prices = prices[prices["facility_id"] != "DC-FRA-01"]
    missing = tmp_path / "prices.csv"
    prices.to_csv(missing, index=False)
    sustainability = CostCarbonEngine(
        ROOT / "database/datacenter.db", missing,
        ROOT / "data/assumptions/carbon_intensity.csv",
        ROOT / "analytics/efficiency_opportunity_weights.yaml",
    )
    with pytest.raises(ValueError, match="exactly one governed assumption"):
        sustainability.daily_model("2025-01-01", "2025-01-01", ["DC-FRA-01"])

    impact = ImpactAnalysisEngine(ROOT / "database/datacenter.db")
    with pytest.raises(ValueError, match="At least three"):
        impact.correlation(
            "pue", "cooling_power_kw", facility_id="DC-FRA-01",
            start_date="2025-01-01", end_date="2025-01-01",
        )
