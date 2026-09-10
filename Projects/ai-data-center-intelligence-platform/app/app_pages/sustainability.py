"""Cost, carbon, and efficiency opportunity page."""

import streamlit as st

from app.ui_shared import load_pipeline


st.caption("Governed modeled energy, cost, carbon, projections, and efficiency scenarios.")
engine = load_pipeline().advanced_chat.sustainability

analysis_type = st.segmented_control(
    "View",
    ["Historical", "Forecast", "Efficiency scenario"],
    default="Historical",
    key="sustainability_view",
)
with st.form("sustainability_controls"):
    if analysis_type == "Forecast":
        year = st.number_input("Forecast year", min_value=2026, max_value=2040, value=2030, step=1)
    else:
        year = st.number_input("Year", min_value=2015, max_value=2025, value=2025, step=1)
    improvement = st.slider(
        "Cooling-efficiency improvement",
        0,
        30,
        10,
        format="%d%%",
        disabled=analysis_type != "Efficiency scenario",
    )
    calculate = st.form_submit_button("Calculate", icon=":material/calculate:", type="primary")

if calculate:
    with st.spinner("Calculating governed cost and carbon metrics…"):
        if analysis_type == "Forecast":
            st.session_state.cost_result = ("forecast", engine.forecast(int(year)))
        elif analysis_type == "Efficiency scenario":
            st.session_state.cost_result = (
                "scenario",
                engine.efficiency_scenario(float(improvement), year=int(year)),
            )
        else:
            st.session_state.cost_result = (
                "historical",
                engine.summarize(f"{int(year)}-01-01", f"{int(year)}-12-31"),
            )

stored = st.session_state.get("cost_result")
if stored:
    kind, result = stored
    frame = result.frame if hasattr(result, "frame") else result
    if kind == "scenario":
        with st.container(horizontal=True):
            st.metric("Energy saved", f"{frame['energy_savings_kwh'].sum():,.0f} kWh", border=True)
            st.metric("Cost saved", f"${frame['cost_savings_usd'].sum():,.0f}", border=True)
            st.metric("Carbon avoided", f"{frame['avoided_carbon_tonnes'].sum():,.2f} tCO2e", border=True)
        st.bar_chart(frame, x="facility_name", y="cost_savings_usd")
    elif kind == "forecast":
        with st.container(horizontal=True):
            st.metric("Projected energy cost", f"${frame['projected_energy_cost_usd'].sum():,.0f}", border=True)
            st.metric("Projected cooling cost", f"${frame['projected_cooling_cost_usd'].sum():,.0f}", border=True)
            st.metric("Projected carbon", f"{frame['projected_carbon_tonnes'].sum():,.2f} tCO2e", border=True)
        st.bar_chart(frame, x="facility_name", y="projected_energy_cost_usd")
        st.warning("Projection from synthetic history and assumptions—not a budget or guarantee.", icon=":material/warning:")
    else:
        with st.container(horizontal=True):
            st.metric("Modeled energy cost", f"${frame['modeled_energy_cost_usd'].sum():,.0f}", border=True)
            st.metric("Modeled cooling cost", f"${frame['modeled_cooling_cost_usd'].sum():,.0f}", border=True)
            st.metric("Modeled carbon", f"{frame['modeled_carbon_tonnes'].sum():,.2f} tCO2e", border=True)
        st.bar_chart(frame, x="facility_name", y="efficiency_opportunity_score")
    st.dataframe(frame, hide_index=True, key="sustainability_result_table")
    st.caption("Daily average kW is modeled over 24 hours. Price and carbon factors are synthetic portfolio-demo assumptions.")
