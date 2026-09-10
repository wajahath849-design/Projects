"""Incident scenario control room."""

import streamlit as st

from app.ui_shared import get_simulation_lab


st.caption("Inject reproducible synthetic incidents without changing historical data.")
lab = get_simulation_lab()
catalog = lab.catalog()
titles = {row["title"]: row["scenario_key"] for row in catalog}
facility_ids = sorted(lab.store._facilities)

with st.form("simulation_setup"):
    scenario_title = st.selectbox("Scenario", list(titles), key="simulation_scenario")
    facility_id = st.selectbox("Target facility", facility_ids, key="simulation_facility")
    speed = st.segmented_control("Playback speed", [1, 2, 5, 10], default=1, key="simulation_speed")
    start = st.form_submit_button("Start scenario", icon=":material/play_arrow:", type="primary")

if start:
    st.session_state.simulation_session_id = lab.start(
        titles[scenario_title], facility_id=facility_id, speed_multiplier=float(speed or 1)
    )
    st.session_state.simulation_last_step = None
    st.toast("Simulation session started", icon=":material/check_circle:")

session_id = st.session_state.get("simulation_session_id")
if session_id:
    session = lab.store.session_row(session_id)
    with st.container(horizontal=True):
        st.metric("Session", session_id, border=True)
        st.metric("Status", str(session["status"]).title(), border=True)
        st.metric("Speed", f"{float(session['speed_multiplier']):g}×", border=True)
        st.metric("Evidence batches", int(session["event_version"]), border=True)
    with st.container(horizontal=True):
        if st.button("Advance", icon=":material/skip_next:", disabled=session["status"] != "running"):
            st.session_state.simulation_last_step = lab.advance(session_id)
            st.rerun()
        if st.button("Run to end", icon=":material/fast_forward:", disabled=session["status"] != "running"):
            steps = lab.run_to_completion(session_id)
            st.session_state.simulation_last_step = steps[-1] if steps else None
            st.rerun()
        if st.button("Pause", icon=":material/pause:", disabled=session["status"] != "running"):
            lab.pause(session_id)
            st.rerun()
        if st.button("Resume", icon=":material/play_arrow:", disabled=session["status"] != "paused"):
            lab.resume(session_id)
            st.rerun()
        if st.button("Reset", icon=":material/restart_alt:"):
            lab.reset(session_id)
            st.session_state.simulation_last_step = None
            st.rerun()
        if st.button("Replay", icon=":material/replay:"):
            lab.replay(session_id)
            st.session_state.simulation_last_step = None
            st.rerun()
    last = st.session_state.get("simulation_last_step")
    if last is not None:
        st.success(
            f"Tick {last.tick_index + 1}/{lab.default_duration_ticks}: {last.phase}; "
            f"{last.batch.event_count} observable records processed.",
            icon=":material/check_circle:",
        )
        st.caption(
            f"Detected {len(last.analytics.anomalies)} new anomalies; "
            f"updated {len(last.analytics.facility_health)} facility health scores."
        )
else:
    st.info("Choose a scenario and start a session.", icon=":material/info:")
