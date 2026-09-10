# Architecture

```text
Raw/external CSVs
  -> adapter + cleaning + canonical contract
  -> processed CSVs
  -> atomic SQLite build
       -> governed KPIs + aggregate tables
       -> linked logs, alerts, maintenance, anomalies, reviews, risk, health
       -> Power BI semantic model and five report-page foundations

User message
  -> relevance/unsafe-action analysis
  -> compact structured context (8 fields)
  -> hybrid intent router
       -> deterministic database/KPI/forecast/scenario/incident/risk/briefing path
       -> or allow-listed RAG + local Ollama structured SQL
  -> independent SQL validation + read-only bounded execution
  -> grounded answer + chart/table + evidence + timing
  -> Streamlit chat / CLI

Private evaluation truth
  -> isolated evaluation runner only
  -X-> production retrieval, prompts, and investigation engines
```

The canonical contract separates source-specific files from every downstream consumer. SQLite is the reproducible analytical source for Python and provides the definitions mirrored by Power Query and DAX.

The router prefers deterministic paths when the intent can be safely calculated: KPIs, comparisons, trends, forecasts, incidents, timelines, anomalies, similarity, recommendations, risk, health, briefing, decisions, and scenarios. Ollama is reserved for flexible historical text-to-SQL and investigative language. This keeps ordinary interactions fast and makes the application useful when the local model is unavailable.

Operational text is untrusted data. Questions, retrieved chunks, log messages, and database records are JSON-serialized inside explicit prompt boundaries. Generated SQL is never trusted: it must be a single allow-listed read-only statement and runs through a read-only connection with row/time limits. Direct infrastructure-control requests stop at a human-authorization gate.

Conversation continuity is explicit rather than transcript-based. The session retains facility, server, original incident, related incident, metric, start date, end date, and analysis mode. This allows natural follow-ups and sequential multi-question handling without leaking an unbounded chat history into prompts.

Forecasts refit annual linear trends from the current database. Scenarios apply a user-supplied percentage to a historical or forecast baseline and preserve the distinction among fact, estimate, assumption, and calculated result. Risk and diagnostic confidence are transparent rule-based triage indicators.

Key tradeoffs: SQLite is single-node; TF-IDF is transparent but less semantic than embeddings; deterministic rendering limits hallucination but can be less expressive; synthetic evidence cannot validate real-world causal performance. A production design would add identity-aware access, a server database, workload isolation, centralized observability, a governed model gateway, and continuous real-data evaluation.
