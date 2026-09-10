"""Conversational operations page."""

import streamlit as st

from app.ui_shared import MODE_OPTIONS, ask_pipeline, render_result


st.caption("Ask natural questions across historical, live, cost, carbon, forecast, incident, and impact data.")

with st.container(horizontal=True, vertical_alignment="bottom"):
    selected_mode = st.selectbox(
        "Analysis mode", list(MODE_OPTIONS), key="copilot_mode", persist_state="session"
    )
    if st.button("New conversation", icon=":material/add_comment:"):
        st.session_state.messages = []
        st.session_state.conversation_context = {}
        st.session_state.recent_questions = []
        st.rerun()

for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant" and message.get("result") is not None:
            render_result(message["result"], f"chat_{index}")
        else:
            st.markdown(message["content"])

suggestions = {
    ":blue[:material/payments:] Forecast cost": "What will the cooling cost and energy price be in 2030?",
    ":green[:material/eco:] Estimate carbon": "What will carbon emissions be in 2030?",
    ":orange[:material/troubleshoot:] Investigate": "What was the incident impact of INC-0000001?",
    ":violet[:material/query_stats:] Compare metrics": "Correlate PUE and cooling power in Frankfurt during 2025",
}
if not st.session_state.messages:
    selected = st.pills("Try asking", list(suggestions), label_visibility="collapsed")
    if selected:
        st.session_state.queued_question = suggestions[selected]
        st.rerun()

typed = st.chat_input(
    "Ask about operations, forecasts, cost, carbon, incidents, or impact",
    submit_mode="disable",
    key="operations_chat_input",
)
question = st.session_state.queued_question or typed
if question:
    st.session_state.queued_question = None
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Grounding the answer in governed data…"):
            result = ask_pipeline(question, MODE_OPTIONS[selected_mode])
        render_result(result, f"chat_{len(st.session_state.messages)}")
    st.session_state.messages.append({"role": "assistant", "content": result.answer, "result": result})
    st.rerun()
