"""Multi-analyst investigation workspace."""

import pandas as pd
import streamlit as st

from app.ui_shared import load_pipeline
from src.investigation.service import MultiAgentInvestigationService


st.caption("Complex incidents invoke specialists selectively; every major finding must reference stored evidence.")
pipeline = load_pipeline()
store = pipeline.advanced_chat.realtime_store
session_id = st.session_state.get("simulation_session_id") or (store.latest_session_id() if store else None)
if not session_id or store is None:
    st.info("Start and advance a scenario before opening an investigation.", icon=":material/info:")
else:
    facility_ids = sorted(store._facilities)
    with st.form("investigation_scope"):
        selected_facility = st.selectbox("Facility scope", ["All facilities", *facility_ids])
        run = st.form_submit_button("Run evidence investigation", icon=":material/troubleshoot:", type="primary")
    if run:
        with st.status("Specialists are reviewing observable evidence…", expanded=True) as status:
            report = MultiAgentInvestigationService(store, pipeline.database_path).investigate(
                session_id, None if selected_facility == "All facilities" else selected_facility
            )
            st.session_state.investigation_report = report
            status.update(label="Investigation complete", state="complete", expanded=False)
    report = st.session_state.get("investigation_report")
    if report is not None:
        with st.container(horizontal=True):
            st.metric("Route", report.route.replace("_", " ").title(), border=True)
            st.metric("Analysts invoked", len(report.invoked_agents), border=True)
            st.metric("Evidence records", len(report.evidence_timeline), border=True)
            st.metric("Confidence", report.confidence_label, border=True)
        st.subheader("Findings")
        st.write(report.incident_summary)
        st.write("**Leading observed contributor:**", report.likely_contributor)
        st.caption(report.uncertainty)
        st.subheader("Analyst summaries")
        st.dataframe(
            pd.DataFrame([
                {
                    "Analyst": item.agent.replace("_", " ").title(),
                    "Finding": item.summary,
                    "Evidence count": len(item.evidence_ids),
                }
                for item in report.findings
            ]),
            hide_index=True,
            key="analyst_summary_table",
        )
        st.subheader("Evidence timeline")
        st.dataframe(
            pd.DataFrame([item.to_dict() for item in report.evidence_timeline]),
            hide_index=True,
            key="investigation_evidence_table",
        )
        with st.expander("Operator inspections", icon=":material/checklist:"):
            for inspection in report.recommended_inspections:
                st.write("-", inspection)
            for guidance in report.maintenance_or_runbook_guidance:
                st.write("-", guidance)
