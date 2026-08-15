# AI-Powered Data Center Operations Intelligence

A portfolio-grade analytics platform combining Python, SQLite, Power BI, retrieval-augmented generation, local Ollama text-to-SQL, SQL security guardrails, and Streamlit. The supplied data is **synthetic data modeling realistic data-center operations** from 2015–2025.

## What is implemented

- Reproducible raw-data profiling, cleaning, and canonical validation for six datasets.
- SQLite analytical model with keys, indexes, views, and reconciled KPI definitions.
- Source-controlled Power BI Project (PBIP), semantic model, DAX measures, three-page dashboard specification, and theme.
- Generic column-alias and external-file adapter with deterministic generated metric IDs.
- Allow-listed TF-IDF RAG over schemas, KPI definitions, glossary terms, relationships, and verified SQL patterns. Evaluation answers are excluded.
- Question relevance, domain, facility, time, module-availability, ambiguity, and unsafe-intent analysis.
- Local Ollama text-to-SQL with structured JSON-schema output (`qwen2.5-coder:7b` by default).
- SQLGlot AST checks, fallback validation, schema allow-listing, one-statement read-only policy, row limits, read-only SQLite, and timeouts.
- Grounded deterministic answers, numerical-claim checks, deterministic Plotly selection, structured logs, terminal CLI, and Streamlit chat UI.
- Database-driven forecasting for 16 energy, cooling, utilization, network, downtime, and incident metrics, with prediction intervals and backtest evidence.
- A 48-question evaluation corpus, 10 explicit SQL security cases, and an offline executable baseline.

## Quick start (Windows PowerShell)

Install Ollama from [ollama.com/download](https://ollama.com/download), then open a new PowerShell window and download the local SQL model:

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

Future-year forecasts use the deterministic local forecasting engine and do not require Ollama. Ollama handles flexible historical natural-language questions.

Then prepare and run the Python project:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python scripts\load_database.py
python scripts\check_ollama.py
python -m pytest -q
python scripts\ask.py "Which facility had the highest average PUE in 2020?"
streamlit run app\streamlit_app.py
```

Install Ollama and run `ollama pull qwen2.5-coder:7b` for general natural-language questions. If Ollama is unavailable, three verified demonstration questions still work offline.

## Main artifacts

- Architecture: [docs/architecture.md](docs/architecture.md)
- Data contract: [docs/data_contract.md](docs/data_contract.md)
- RAG and AI design: [docs/rag_design.md](docs/rag_design.md)
- Evaluation: [docs/evaluation.md](docs/evaluation.md)
- Forecasting: [docs/forecasting.md](docs/forecasting.md)
- Remaining-stage implementation guide: [docs/steps8_20_implementation.md](docs/steps8_20_implementation.md)
- Power BI project: [powerbi/PBI/DataCenter Operations Foundation.pbip](powerbi/PBI/DataCenter%20Operations%20Foundation.pbip)
- Dashboard layout: [powerbi/documentation/dashboard_pages.md](powerbi/documentation/dashboard_pages.md)

## Honest limitations

- Full local-model result accuracy is not reported until the complete evaluation corpus is run on the user's machine.
- Local generation speed and SQL quality depend on available CPU, GPU, memory, and selected model size.
- The PBIP source is generated and test-validated, but final pixel-level review and `.pbix` export require Power BI Desktop.
- SQLite, TF-IDF retrieval, and Streamlit are appropriate for this portfolio-scale workload; a production deployment would add identity, a server database, centralized observability, workload isolation, and governed model evaluation.
