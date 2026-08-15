# Portfolio, CV, LinkedIn, and Interview Guide

## CV bullets

- Built an AI-powered data-center operations analytics platform over synthetic 2015–2025 data using Python, SQLite, Power BI, Streamlit, RAG, and local Ollama text-to-SQL.
- Implemented a canonical six-table data model, reproducible quality/cleaning pipelines, shared KPI definitions, external-schema mapping, and read-only SQL execution guarded by SQLGlot AST and schema validation.
- Created a 48-question evaluation corpus and automated tests covering data quality, KPI reconciliation, retrieval, ambiguity handling, SQL injection defenses, answer grounding, and end-to-end execution.

## LinkedIn description

I built an AI-powered data-center operations intelligence platform using synthetic data that models realistic facility, server, power, cooling, network, downtime, and incident operations from 2015–2025. Power BI provides KPI monitoring and long-term analysis, while a Streamlit assistant retrieves approved schema and metric context, generates SQL with a local Ollama model, validates it with read-only security controls, executes it against SQLite, and returns grounded results with deterministic visualizations. The repository also includes external-dataset mapping and a tiered evaluation suite. The published measurements are limited to the offline baseline; general local-model accuracy has not been claimed without a full evaluation run.

## Portfolio summary

The project demonstrates a complete analytics-engineering and trustworthy-AI workflow: data profiling, ETL, dimensional modeling, KPI governance, BI modeling, RAG, text-to-SQL, defensive query execution, explainable results, evaluation, and testing. Its main design principle is separation of concerns: model output proposes a query, deterministic controls authorize it, and database results remain the source of truth.

## Technical skills

Python, pandas, NumPy, SQL, SQLite, dimensional modeling, Power BI, Power Query, DAX, Streamlit, Plotly, Ollama, local LLMs, RAG, TF-IDF, SQLGlot, pytest, data quality, ETL, semantic layers, prompt-injection defense, and analytical evaluation.

## Interview questions

**Why use a star-like analytical model?** It keeps dimensions such as facility/server separate from metric facts, reduces duplication, and makes joins and BI filtering predictable.

**How do indexes help?** They reduce scanning for common facility/date/server filters, at the cost of storage and slower writes—which is acceptable for a read-heavy analytical database.

**How does RAG differ from model training?** RAG supplies selected context at request time; it does not change model weights and is easier to update and audit.

**Can SQLGlot make LLM SQL perfectly safe?** No. It strengthens syntactic and structural checks, but production also needs identity, permissions, workload limits, audited views, isolation, and continuous red-team testing.

**How do you avoid causal overclaiming?** Investigative answers describe correlations and temporal coincidence unless the data and methodology support causal inference.

**How would PostgreSQL change the design?** Use a restricted database role, statement timeout, connection pooling, governed schemas/views, row-level security where needed, and query-cost monitoring.

**What are the largest limitations?** Synthetic data, a local single-user database, lexical retrieval, a small reviewed ground-truth subset, no measured general LLM accuracy yet, and a Power BI artifact that still needs desktop visual acceptance testing.
