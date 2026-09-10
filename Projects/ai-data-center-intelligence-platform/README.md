# AI-Powered Data Center Operations & Reliability Copilot

A portfolio-grade operations intelligence platform combining Python, SQLite, Power BI, retrieval-augmented generation, local Ollama text-to-SQL, guarded forecasting and scenarios, and a Streamlit operations chat. The supplied 2015–2025 data and all operational evidence are **synthetic data modeling realistic data-center operations**.

## Implemented capabilities

- Reproducible profiling, cleaning, canonical validation, and atomic SQLite rebuilds.
- A governed analytical model with 18 reconciled KPIs, indexes, views, yearly/monthly aggregates, and read-only access.
- Linked system logs, alerts, maintenance actions, anomalies, incident reviews, server-risk scores, and facility-health scores.
- Timeline reconstruction, incident investigation, evidence review, first-signal detection, similar incidents, approved incident learning, cautious root-cause categorization, and runbook recommendations.
- A hybrid router for deterministic analytics, definitions, forecasts, investigations, risks, health, briefings, decisions, scenarios, and flexible local-AI questions.
- Compact eight-field conversational memory for facility, server, original/related incident, metric, dates, and analysis mode; multiple questions run sequentially.
- Database-refitted forecasts for 16 time-varying metrics, with prediction intervals and backtest evidence. Missing dates trigger a counter-question.
- Metric-aware what-if analysis for every supported forecast metric. Baseline facts or forecasts, assumptions, results, and differences remain separate.
- Local Ollama structured text-to-SQL (`qwen2.5-coder:7b` by default) for flexible historical questions.
- Allow-listed routed TF-IDF retrieval over schemas, KPIs, glossary, forecast definitions, SQL examples, incident knowledge, runbooks, and error codes. Evaluation truth is excluded.
- SQLGlot checks, schema allow-listing, one-statement read-only policy, row/time limits, prompt-injection boundaries, numerical-answer validation, and a human approval gate for operational actions.
- Native Streamlit chat with starter prompts, evidence and timing panels, incident cards, monthly operations briefing, facility health, and server-risk views.
- Source-controlled Power BI executive dashboard with 17 semantic tables, 30 relationships, 56 DAX measures, 7 populated pages, 223 native visuals, Power Query, and a custom theme.

## Quick start on Windows

Install Ollama from [ollama.com/download](https://ollama.com/download), then:

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

Prepare and run the project:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\bootstrap_github.py
python scripts\check_ollama.py
python -m pytest -q
streamlit run app\streamlit_app.py
```

`bootstrap_github.py` restores the bundled synthetic processed dataset when it
is not already present and builds the ignored local SQLite database. Large raw,
cleaned, generated, database, cache, and log files are intentionally excluded
from Git.

Open `http://localhost:8501`. Forecasts, database analytics, briefings, risk/health views, incident workflows, and scenarios work deterministically without Ollama. Ollama expands flexible natural-language analytics.

Useful release checks:

```powershell
python scripts\benchmark_log_search.py
python scripts\benchmark_rag_routing.py
python evaluation\evaluate_root_cause.py
python scripts\validate_advanced_release.py
```

## Try these conversations

```text
What happened in Frankfurt on July 14, 2025?
Show the evidence
What happened first?
Have we seen this before?
How was the closest one fixed?
Could this happen again?
What should we inspect?
What if we upgrade the cooling system by 15%?
```

Other examples:

```text
What will cooling cost be in 2030?
Compare PUE in 2015, 2020, and 2025
What will network latency and packet loss be in 2040?
Which facility should we prioritize for an efficiency upgrade?
What if network throughput improves by 10% in 2030?
```

## Documentation and evidence

- [Architecture](docs/architecture.md)
- [Data contract](docs/data_contract.md)
- [Evaluation](docs/evaluation.md)
- [Forecasting](docs/forecasting.md)
- [Final advanced release status](docs/advanced_release_status.md)
- [Final chat behavior](docs/final_chat_phase34.md)
- [Security and human control](docs/security_human_control_phases31_33.md)
- [Performance phases 1–4](docs/performance_phase1.md), [phase 2](docs/performance_phase2.md), [phase 3](docs/performance_phase3.md), [phase 4](docs/performance_phase4.md)
- [Operational evidence phases 5–7](docs/operational_evidence_phases5_7.md)
- [Incident RAG phases 8–9](docs/incident_knowledge_phases8_9.md)
- [Anomaly detection phase 10](docs/anomaly_detection_phase10.md)
- [Incident intelligence phases 11–14](docs/incident_intelligence_phases11_14.md)
- [Risk and health phases 15–16](docs/risk_health_phases15_16.md)
- [Decision and scenarios phases 17–18](docs/decision_scenario_phases17_18.md)
- [Chat intelligence phases 19–22](docs/chat_intelligence_phases19_22.md)
- [Briefing and UI phases 23–25](docs/briefing_ui_phases23_25.md)
- [Power BI and performance phases 26–29](docs/powerbi_performance_phases26_29.md)
- [Power BI project](powerbi/PBI/DataCenter%20Executive%20Dashboard.pbip)

## Honest limitations

- Full local-model corpus accuracy and latency depend on the user's installed Ollama model and hardware; offline deterministic evidence is reported separately.
- Forecasts are linear-trend projections trained on synthetic 2015–2025 observations. Prediction intervals do not make them guarantees.
- Risk, health, diagnosis, decisions, and scenario outputs are explainable triage aids. They do not authorize or execute infrastructure changes.
- PBIP source is generated and statically test-validated. Final refresh, cross-filter, pixel review, and `.pbix` export require Power BI Desktop.
- SQLite, TF-IDF, and Streamlit fit this portfolio workload. Production deployment would add identity, a server database, centralized observability, workload isolation, and governed model monitoring.
