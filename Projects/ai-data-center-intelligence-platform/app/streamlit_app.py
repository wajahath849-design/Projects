"""Entry point for the multi-page data-center operations workbench."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui_shared import initialize_state
from src.question_analyzer import FACILITIES


st.set_page_config(
    page_title="Data center operations intelligence",
    page_icon=":material/domain:",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_state()

pages = {
    "": [
        st.Page("app_pages/copilot.py", title="Operations copilot", icon=":material/chat:"),
        st.Page("app_pages/live_ops.py", title="Live ops", icon=":material/pulse_alert:"),
    ],
    "Investigate": [
        st.Page("app_pages/simulation_lab.py", title="Simulation lab", icon=":material/experiment:"),
        st.Page("app_pages/investigation.py", title="Investigation", icon=":material/troubleshoot:"),
    ],
    "Analyze": [
        st.Page("app_pages/sustainability.py", title="Cost & sustainability", icon=":material/energy_savings_leaf:"),
        st.Page("app_pages/impact.py", title="Impact analysis", icon=":material/query_stats:"),
    ],
}
page = st.navigation(pages, position="top")

with st.sidebar:
    st.header("Operations intelligence")
    st.caption("Synthetic 2015–2025 history with isolated live simulation")
    st.badge("Canonical data ready", icon=":material/check_circle:", color="green")
    st.selectbox(
        "Facility",
        ["All facilities", *sorted(set(FACILITIES.values()))],
        key="global_facility",
        persist_state="session",
    )
    st.toggle(
        "Apply historical date filter",
        key="global_apply_date_filter",
        persist_state="session",
    )
    st.date_input(
        "Historical date range",
        value=(pd.Timestamp("2025-01-01").date(), pd.Timestamp("2025-12-31").date()),
        disabled=not st.session_state.global_apply_date_filter,
        key="global_date_range",
        persist_state="session",
    )
    st.caption("6 facilities · 430 servers · 1,158 incidents")
    st.caption("All operational records and external factors are synthetic. Operator approval is required for actions.")

st.title(f"{page.icon} {page.title}")
page.run()
