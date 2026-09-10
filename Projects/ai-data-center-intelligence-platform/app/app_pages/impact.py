"""Correlation, incident, and intervention impact page."""

import pandas as pd
import streamlit as st

from app.ui_shared import load_pipeline


st.caption("Evidence levels remain explicit: association, temporal ordering, incident comparison, or guarded intervention estimate.")
pipeline = load_pipeline()
engine = pipeline.advanced_chat.impact
view = st.segmented_control(
    "Analysis",
    ["Correlation", "Lead-lag", "Incident impact", "Intervention"],
    default="Correlation",
    key="impact_view",
)
metric_options = list(engine.METRIC_COLUMNS)
facility_options = sorted(
    pipeline.advanced_chat.realtime_store._facilities
    if pipeline.advanced_chat.realtime_store else
    ["DC-FRA-01", "DC-DUB-01", "DC-IAD-01", "DC-PDX-01", "DC-SIN-01", "DC-SYD-01"]
)
with st.form("impact_controls"):
    if view in {"Correlation", "Lead-lag"}:
        metric_x = st.selectbox("First metric", metric_options, index=0)
        metric_y = st.selectbox("Second metric", metric_options, index=3)
        facility = st.selectbox("Facility", facility_options)
    elif view == "Incident impact":
        incident_id = st.text_input("Incident ID", value="INC-0000001")
    else:
        outcome = st.selectbox("Outcome metric", metric_options)
        intervention_date = st.date_input(
            "Intervention date", value=pd.Timestamp("2025-01-01").date()
        )
        treated = st.selectbox("Treated facility", facility_options)
        comparison = st.selectbox("Comparison facility", ["None", *facility_options])
    run = st.form_submit_button("Run analysis", icon=":material/query_stats:", type="primary")

if run:
    try:
        if view == "Correlation":
            st.session_state.impact_result = (
                "correlation",
                engine.correlation(metric_x, metric_y, facility_id=facility),
            )
        elif view == "Lead-lag":
            st.session_state.impact_result = (
                "lead_lag",
                engine.lead_lag(metric_x, metric_y, facility_id=facility),
            )
        elif view == "Incident impact":
            st.session_state.impact_result = (
                "incident",
                engine.incident_impact(incident_id.strip().upper()),
            )
        else:
            st.session_state.impact_result = (
                "intervention",
                engine.intervention(
                    outcome,
                    intervention_date.isoformat(),
                    treated_facility_id=treated,
                    comparison_facility_id=None if comparison == "None" else comparison,
                ),
            )
    except (ValueError, LookupError) as error:
        st.error(str(error), icon=":material/error:")

stored = st.session_state.get("impact_result")
if stored:
    kind, result = stored
    if kind == "correlation":
        with st.container(horizontal=True):
            st.metric("Coefficient", f"{result.coefficient:.3f}", border=True)
            st.metric("Sample size", result.sample_size, border=True)
            st.metric("Scope", result.scope, border=True)
        st.scatter_chart(result.chart_data, x=result.metric_x, y=result.metric_y)
        st.warning(result.interpretation, icon=":material/warning:")
    elif kind == "lead_lag":
        st.line_chart(result, x="lag_days", y="coefficient")
        st.caption("Positive lag means the first metric appears before the outcome. This is not causal evidence.")
        st.dataframe(result, hide_index=True, key="lead_lag_table")
    elif kind == "incident":
        metrics = pd.DataFrame(result["metrics"])
        with st.container(horizontal=True):
            st.metric("Incident", result["incident_id"], border=True)
            st.metric("Duration", f"{result['duration_minutes']} min", border=True)
            st.metric("Affected servers", result["affected_servers_same_facility_day"], border=True)
        st.bar_chart(metrics, x="metric", y="during_change_pct")
        st.dataframe(metrics, hide_index=True, key="incident_impact_table")
        st.warning(result["caveat"], icon=":material/warning:")
    else:
        with st.container(horizontal=True):
            st.metric("Method", result.method.replace("_", " ").title(), border=True)
            st.metric("Estimated change", f"{result.estimated_change:,.4f} {result.unit}", border=True)
            st.metric("Evidence", result.evidence_score["overall_qualitative"], border=True)
        st.line_chart(result.chart_data, x="date", y="value", color="facility_id")
        st.warning(result.interpretation, icon=":material/warning:")
        with st.expander("Method checks", icon=":material/fact_check:"):
            st.json({
                "met": result.assumptions_met,
                "failed": result.assumptions_failed,
                "evidence_score": result.evidence_score,
            })
