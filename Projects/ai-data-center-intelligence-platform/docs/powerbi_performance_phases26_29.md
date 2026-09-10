# Phases 26–29: Power BI and Advanced Performance

## Power BI enhancement

The source-controlled PBIP model now imports six additional governed facts: logs, alerts, maintenance actions, anomalies, server risk, and facility health. The semantic model contains 14 tables and 25 single-direction relationships. Inactive server relationships prevent ambiguous facility-to-fact paths.

Two page foundations were added:

- **Reliability & Incident Intelligence** — incident, downtime, MTTR, alerts, logs, anomalies, components, repeated causes, and detail lookup;
- **Predictive Operations** — server risk, health score, capacity pressure, and explicitly labelled trend views.

New DAX measures use the same canonical fields and meanings as SQLite and Python. Power BI trend lines are not labelled as forecasts; governed forecast extracts remain separate until versioned into the semantic model.

The dashboard brief follows a summary → trend → diagnosis → detail hierarchy. Global date and facility filters remain the primary controls, and the latest-data-date measure makes freshness visible.

## Operational aggregates

`agg_facility_monthly_operations` precomputes complete facility-month counts for logs, errors, critical logs, alerts, incidents, downtime, anomalies, and maintenance actions. `agg_event_code_monthly` precomputes component/event/severity counts. These avoid scanning detailed operational evidence for recurring monitoring questions.

The original `agg_facility_yearly` remains unchanged and continues to protect forecasts and historical analytics from scans of 1.7 million server measurements.

## Log search indexes and benchmark

The supported access paths now have indexes for:

- timestamp;
- facility + timestamp;
- server + timestamp;
- event code + timestamp;
- component + timestamp;
- log level + timestamp.

`scripts/benchmark_log_search.py` copies only `system_logs` into an in-memory SQLite database, benchmarks the current index set, adds proposed indexes, reruns identical parameterized queries, and records `EXPLAIN QUERY PLAN` plus P50/P95. The canonical database remains read-only during comparison.

The accepted 28 August 2026 run used 5,790 log rows and 100 repetitions. P50 improved from 0.8400 to 0.3590 ms for the global time window, 1.4843 to 0.3262 ms for component history, and 0.8098 to 0.0903 ms for severity history. Query plans selected the new timestamp, component/timestamp, and level/timestamp indexes. Facility, server, and event-code access paths retained their existing composite indexes. Evidence is recorded in `evaluation/results/log_search_phase28.json`.

## Routed RAG performance

RAG now builds separate TF-IDF matrices for schema, KPI definitions, glossary, forecast definitions, SQL examples, incident knowledge, runbooks, and error codes. A routed request transforms and compares only the selected matrices; it no longer computes full-corpus similarity and filters afterward.

Exact event-code questions use an exact-code first path, followed only by error-code and runbook context. SQL generation never searches runbooks. Incident investigations never search the SQL or KPI collections.

`scripts/benchmark_rag_routing.py` compares full-corpus and routed P50 latency plus collection precision across representative questions. The accepted 200-repetition run reduced P50 from 0.8752 to 0.5116 ms with mean routing precision 0.8333. Evidence is recorded in `evaluation/results/rag_routing_phase29.json`.

## Dashboard QA status

Source files, page order, table count, relationship count, Power Query coverage, DAX presence, and JSON page metadata have static tests. Power BI Desktop refresh, visual binding, cross-filter behavior, pixel review, and `.pbix` export remain desktop-only checks.

## Skill influence

The dashboard-building workflow kept the canonical processed extracts as the source of truth, used existing semantic definitions instead of parallel calculations, organized pages around operator decisions, limited global filters, and documented unresolved refresh/render checks rather than claiming a published dashboard.
