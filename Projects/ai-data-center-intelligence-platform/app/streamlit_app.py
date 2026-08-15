from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import AnalyticsPipeline
from src.config import settings
from src.sql_generator import OllamaSQLGenerator
from src.visualizer import build_plotly_chart


st.set_page_config(page_title="Data Center Intelligence", page_icon="🏢", layout="wide")
st.title("AI Data Center Operations Intelligence")
st.caption("Ask grounded questions about synthetic 2015–2025 energy, server, network, and reliability data.")

with st.sidebar:
    st.header("Example questions")
    st.markdown(
        "- Which facility had the highest average PUE in 2020?\n"
        "- Which facility had the most downtime per server?\n"
        "- How did cooling costs change between 2017 and 2025?\n"
        "- Estimate the price of cooling in 2030.\n"
        "- What will network latency be in 2030?"
    )
    st.info("General questions use a local Ollama model. The examples above also work in offline demonstration mode.")
    if OllamaSQLGenerator.model_available(settings.ollama_host, settings.ollama_model):
        st.success(f"Local AI ready ({settings.ollama_model})")
    elif OllamaSQLGenerator.server_available(settings.ollama_host):
        st.warning(f"Ollama is running, but {settings.ollama_model} is not installed. Run: ollama pull {settings.ollama_model}")
    else:
        st.warning("Offline mode: install/start Ollama, pull the configured model, then restart Streamlit.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pipeline" not in st.session_state:
    try:
        st.session_state.pipeline = AnalyticsPipeline()
    except Exception as error:
        st.error(f"The analytics engine could not start: {error}")
        st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if question := st.chat_input("Ask an operational analytics question"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing the data…"):
            result = st.session_state.pipeline.ask(question)
        st.markdown(result.answer)
        if result.status == "forecast":
            st.warning("Forecast values are statistical projections from synthetic historical data, not observed results or guarantees.")
        if result.frame is not None:
            chart = build_plotly_chart(result.frame, result.chart)
            if chart is not None:
                st.plotly_chart(chart, use_container_width=True)
            st.dataframe(result.frame, use_container_width=True, hide_index=True)
        with st.expander("Technical details"):
            st.write(f"Status: {result.status}")
            st.write(f"SQL validation: {result.validation_status or 'not run'}")
            if result.sql:
                st.code(result.sql, language="sql")
            st.write("Source tables:", result.source_tables or [])
            st.write("Retrieved context:", result.retrieved_context or [])
            if result.execution_ms is not None:
                st.write(f"SQL execution: {result.execution_ms:.1f} ms")
    st.session_state.messages.append({"role": "assistant", "content": result.answer})
