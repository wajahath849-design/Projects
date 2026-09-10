"""Shared Streamlit resources, state, and safe result rendering."""

from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from src.config import settings
from src.performance import TIMING_STAGES
from src.pipeline import AnalyticsPipeline
from src.realtime.configuration import RealtimeConfig
from src.realtime.simulator import TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService
from src.simulation.lab import IncidentSimulationLab


PIPELINE_STATE_VERSION = "operations-intelligence-phase-j-v1"
MODE_OPTIONS = {
    "Auto": None,
    "Live status": "REALTIME_STATUS",
    "Specialist investigation": "MULTI_AGENT_INVESTIGATION",
    "Cost analysis": "COST_ANALYSIS",
    "Carbon analysis": "CARBON_ANALYSIS",
    "Efficiency scenario": "EFFICIENCY_SCENARIO",
    "Impact analysis": "IMPACT_ANALYSIS",
    "Correlation": "CORRELATION_ANALYSIS",
    "Intervention": "INTERVENTION_ANALYSIS",
    "Incident investigation": "INCIDENT_INVESTIGATION",
    "Anomaly investigation": "ANOMALY_INVESTIGATION",
    "Predictive maintenance": "PREDICTIVE_MAINTENANCE",
    "Decision support": "DECISION_SUPPORT",
}


@st.cache_resource(show_spinner=False)
def load_pipeline(version: str = PIPELINE_STATE_VERSION) -> AnalyticsPipeline:
    del version
    return AnalyticsPipeline()


def initialize_state() -> None:
    defaults = {
        "messages": [],
        "conversation_context": {},
        "recent_questions": [],
        "queued_question": None,
        "briefing": None,
        "global_facility": "All facilities",
        "global_apply_date_filter": False,
        "simulation_session_id": None,
        "simulation_last_step": None,
        "investigation_report": None,
        "cost_result": None,
        "impact_result": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_simulation_lab() -> IncidentSimulationLab:
    if "simulation_lab_resource" not in st.session_state:
        config = RealtimeConfig.from_yaml(settings.realtime_config_path)
        store = RealtimeStore(
            settings.realtime_database_path,
            settings.database_path,
            settings.project_root / "database/realtime_schema.sql",
        )
        store.initialize()
        simulator = TelemetrySimulator(
            settings.database_path,
            random_seed=config.random_seed,
            tick_interval_seconds=config.tick_interval_seconds,
            server_sample_size_per_facility=config.server_sample_size_per_facility,
        )
        analytics = StreamingAnalyticsService(
            store, config, settings.project_root / "analytics/live_health_weights.yaml"
        )
        st.session_state.simulation_lab_resource = IncidentSimulationLab(
            store, simulator, analytics, settings.project_root / "config/simulation_scenarios.yaml"
        )
    return st.session_state.simulation_lab_resource


def global_context() -> dict[str, object]:
    context = dict(st.session_state.get("conversation_context", {}))
    facility = st.session_state.get("global_facility", "All facilities")
    if facility != "All facilities":
        context["facilities"] = (facility,)
    if st.session_state.get("global_apply_date_filter"):
        dates = st.session_state.get("global_date_range")
        if isinstance(dates, tuple) and len(dates) == 2:
            context["start_date"] = dates[0].isoformat()
            context["end_date"] = dates[1].isoformat()
    session_id = st.session_state.get("simulation_session_id")
    if session_id:
        context["simulation_session_id"] = session_id
    return context


def ask_pipeline(question: str, requested_mode: str | None = None):
    pipeline = load_pipeline()
    started = time.perf_counter()
    result = pipeline.ask(
        question,
        upstream_timings={"memory_resolution_ms": (time.perf_counter() - started) * 1000},
        conversation_context=global_context(),
        requested_mode=requested_mode,
    )
    st.session_state.conversation_context = result.conversation_context or global_context()
    return result


def _render_native_chart(frame: pd.DataFrame, spec: dict[str, object] | None, key: str) -> None:
    if not spec or frame.empty:
        return
    kind = spec.get("kind")
    x, y = spec.get("x"), spec.get("y")
    if not isinstance(x, str) or not isinstance(y, str) or x not in frame or y not in frame:
        return
    color = spec.get("color") if isinstance(spec.get("color"), str) and spec.get("color") in frame else None
    if kind == "line":
        st.line_chart(frame, x=x, y=y, color=color, key=f"{key}_line")
    elif kind == "bar":
        st.bar_chart(frame, x=x, y=y, color=color, key=f"{key}_bar")
    elif kind == "scatter":
        st.scatter_chart(frame, x=x, y=y, color=color, key=f"{key}_scatter")


def render_result(result, key_prefix: str) -> None:
    st.markdown(result.answer)
    if result.status in {"forecast", "forecast_direction", "cost_forecast", "carbon_forecast"}:
        st.warning("Forecasts are estimates from synthetic history and explicit assumptions—not observed values or guarantees.", icon=":material/warning:")
    if result.status in {"scenario", "efficiency_scenario"}:
        st.info("Scenario results apply a user assumption and do not predict a guaranteed outcome.", icon=":material/info:")
    if result.status == "approval_required":
        st.warning("No action was executed. Operator authorization is required.", icon=":material/lock:")
    if result.frame is not None and not result.frame.empty:
        _render_native_chart(result.frame, result.chart, key_prefix)
        st.dataframe(result.frame, hide_index=True, key=f"{key_prefix}_table")
    if result.evidence_panel:
        with st.expander("Evidence", icon=":material/fact_check:"):
            st.json(result.evidence_panel, expanded=False)
    with st.expander("Technical details", icon=":material/settings:"):
        with st.container(horizontal=True):
            st.metric("Route", result.execution_path or "—", border=True)
            st.metric("Rows", result.row_count or 0, border=True)
            st.metric("Local-AI calls", result.llm_calls, border=True)
            st.metric("Total time", f"{result.total_ms:.1f} ms" if result.total_ms is not None else "—", border=True)
        st.caption(f"Mode: {result.analysis_mode} · Validation: {result.validation_status or 'not run'}")
        st.caption("Sources: " + ", ".join(result.source_tables or []))
        if result.timings:
            st.dataframe(
                [{"Stage": stage.removesuffix("_ms").replace("_", " ").title(), "Milliseconds": result.timings.get(stage, 0.0)} for stage in TIMING_STAGES],
                hide_index=True,
                key=f"{key_prefix}_timings",
            )
