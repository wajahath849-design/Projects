"""Auto-refreshing live operations status."""

import pandas as pd
import streamlit as st

from app.ui_shared import load_pipeline
from src.conversation_context import ConversationContext


st.caption("Current simulation telemetry, alerts, anomalies, and facility health. Refreshes every five seconds while open.")


@st.fragment(run_every="5s")
def live_status() -> None:
    pipeline = load_pipeline()
    store = pipeline.advanced_chat.realtime_store
    streaming = pipeline.advanced_chat.streaming
    session_id = st.session_state.get("simulation_session_id") or (store.latest_session_id() if store else None)
    if not session_id or streaming is None:
        st.info("Start a scenario in the Simulation lab to populate live operations.", icon=":material/info:")
        return
    facility = st.session_state.get("global_facility", "All facilities")
    facility_id = None
    if facility != "All facilities":
        facility_ids = pipeline.advanced_chat._facility_ids(ConversationContext(facilities=(facility,)))
        facility_id = facility_ids[0] if facility_ids else None
    status = streaming.current_status(session_id, facility_id)
    health = pd.DataFrame(status.facility_health)
    anomalies = pd.DataFrame(status.active_anomalies)
    alerts = pd.DataFrame(status.active_alerts)
    with st.container(horizontal=True):
        st.metric("Session", session_id, border=True)
        st.metric("State current", "Yes" if status.state_is_current else "No", border=True)
        st.metric("Active anomalies", len(anomalies), border=True)
        st.metric("Active alerts", len(alerts), border=True)
    if not health.empty:
        st.subheader("Facility health")
        st.bar_chart(health, x="facility_id", y="health_score")
        st.dataframe(
            health[["facility_id", "health_score", "data_completeness_pct", "active_alert_count", "active_anomaly_count"]],
            hide_index=True, key="live_health_table",
        )
    left, right = st.columns(2)
    with left.container(border=True, height="stretch"):
        st.subheader("Active anomalies")
        if anomalies.empty:
            st.caption("No active anomalies.")
        else:
            st.dataframe(anomalies, hide_index=True, key="live_anomalies_table")
    with right.container(border=True, height="stretch"):
        st.subheader("Active alerts")
        if alerts.empty:
            st.caption("No active alerts.")
        else:
            st.dataframe(alerts, hide_index=True, key="live_alerts_table")


live_status()
