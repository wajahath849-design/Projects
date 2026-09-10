# Phase 1 Performance Profiling

## Scope

This phase instruments and benchmarks the existing application. It does not add query templates, caches, summary tables, indexes, prompt reductions, model keep-alive settings, or definition fast paths. SQL validation, read-only execution, forecasting behavior, RAG retrieval, and answer generation remain functionally unchanged.

## Measurement method

- Benchmark: 30 sequential questions from `evaluation/performance_questions.json`.
- Runtime: local Ollama with `qwen2.5-coder:7b`, observed at 100% CPU with a 4096-token context.
- Database: SQLite, 270.21 MB, containing the current synthetic 2015-2025 dataset.
- Workload: definitions, simple KPIs, comparisons, trends, large aggregations, complex analysis, forecasts, follow-ups, ambiguity, out-of-scope, security, and clarification.
- Result: `evaluation/results/performance_baseline.json`.
- Each question was executed once. Category samples are intentionally small, so category percentiles are baseline indicators rather than production service-level estimates.
- `chart_generation_ms` measures Python-side chart construction, not browser painting.

Pipeline initialization took **1,331.9 ms** and is reported separately from per-question latency.

## Answer: exactly where is the user waiting?

The user is waiting almost entirely for local Ollama inference on questions routed to the AI path.

- Total measured request time across the suite: **571.18 seconds**.
- Time inside measured LLM SQL/answer stages: **565.61 seconds (99.03%)**.
- Questions making at least one LLM call: **10 of 30**.
- Total LLM calls: **15**.
- SQLite execution P95: **51.24 ms**; maximum: **93.84 ms**.
- RAG retrieval P95: **3.17 ms**; maximum: **3.86 ms**.
- Routing P95: **3.20 ms**; memory resolution P95: **2.59 ms**.

SQLite and TF-IDF retrieval are not the primary bottlenecks in this measured workload.

## Overall baseline

| Metric | Measured value |
|---|---:|
| P50 total latency | 106.89 ms |
| P95 total latency | 64,408.72 ms |
| Maximum total latency | 169,480.43 ms |
| Mean total latency | 19,039.22 ms |
| P50 database latency | 0.00 ms |
| P95 database latency | 51.24 ms |
| P50 measured LLM-stage latency | 0.68 ms |
| P95 measured LLM-stage latency | 64,384.87 ms |
| Cache hit rate | 0% (cache not implemented) |

The mixed-workload P50 is low because 20 questions used no LLM. The path-specific results below are more useful for architecture decisions.

## Latency by execution path

| Current execution path | Questions | P50 | P95 | Maximum |
|---|---:|---:|---:|---:|
| AI definition | 2 | 25,723.51 ms | 35,040.43 ms | 36,075.64 ms |
| AI text-to-SQL | 8 | 46,763.65 ms | 134,402.18 ms | 169,480.43 ms |
| Deterministic historical | 5 | 63.37 ms | 566.67 ms | 686.74 ms |
| Forecast | 10 | 67.53 ms | 2,010.97 ms | 3,508.44 ms |
| Router only | 5 | 3.25 ms | 8.51 ms | 9.73 ms |

Execution-path usage in this corpus was 33.33% forecast, 26.67% AI text-to-SQL, 16.67% deterministic historical, 16.67% router-only, and 6.67% AI definition.

## Stage measurements

| Stage | P50 | P95 | Maximum | Finding |
|---|---:|---:|---:|---|
| Router | 1.37 ms | 3.20 ms | 5.37 ms | Negligible latency |
| Memory resolution | 1.78 ms | 2.59 ms | 5.11 ms | Negligible latency |
| RAG retrieval | 0.00 ms | 3.17 ms | 3.86 ms | Index lookup is already fast per request |
| LLM SQL generation | 0.00 ms | 53,768.29 ms | 59,578.32 ms | Dominant on AI SQL requests |
| SQL validation | 0.00 ms | 4.12 ms | 124.72 ms | Small; maximum likely includes first import/setup work |
| Database execution | 0.00 ms | 51.24 ms | 93.84 ms | Not the primary bottleneck in this corpus |
| Answer generation | 0.21 ms | 26,749.61 ms | 137,508.36 ms | Dominant when a narrative answer is generated |
| Chart generation | 8.72 ms | 48.23 ms | 583.80 ms | First Plotly construction produces a visible cold-start cost |
| Forecast | 0.00 ms | 123.24 ms | 3,484.13 ms | CPU forecast over raw server history is the main non-LLM hotspot |

## Notable individual observations

- `Count incidents by facility and root cause` took **169.48 seconds**. SQL generation used about 31.90 seconds and answer generation used about 137.51 seconds; database execution used about 12.43 ms.
- `Which facility had the highest average PUE in 2020?` took **69.26 seconds**, almost entirely in its two LLM calls.
- The first deterministic comparison took **686.74 ms**, including **583.80 ms** for the first Python-side Plotly construction. Later chart construction was substantially faster.
- `Forecast CPU utilization in 2030` took **3.51 seconds**, with **3.48 seconds** in forecasting. This metric reads and aggregates the large server history, making it the clearest measured candidate for later aggregate/forecast caching.
- Follow-up questions had a **49.35 ms P50**, showing that compact structured memory itself is not a bottleneck.

## Correctness and routing findings discovered by profiling

The benchmark harness completed all 30 questions, but the current pipeline produced three SQL execution errors:

1. Incident count used a nonexistent `incident_date` column instead of `start_time`.
2. CPU-by-facility joined `server_metrics` directly to `facilities` through an invalid `server_id` relationship.
3. Memory-by-facility used the same invalid relationship.

The current validator checks whether a column exists somewhere in the schema but does not fully verify that a qualified column belongs to the referenced table. The independent guardrail remained active, but this is a correctness-validation gap to address in a later phase.

Additional baseline limitations:

- One complex reliability question was rejected as out of scope in 9.73 ms, showing a router vocabulary gap.
- Several AI-path requests returned empty or non-useful results because generated filters used informal facility names or incorrect query semantics.
- One otherwise correct PUE result fell back to the authoritative table because the answer used unsupported numeric precision.

No accuracy percentage is claimed from this performance benchmark because these questions were not result-scored against ground truth in this phase.

## Instrumentation added

Every `PipelineResult` and analytics log entry now includes:

- `total_ms`
- `routing_ms`
- `memory_resolution_ms`
- `rag_retrieval_ms`
- `llm_sql_generation_ms`
- `sql_validation_ms`
- `database_execution_ms`
- `answer_generation_ms`
- `chart_generation_ms`
- `forecast_ms`
- execution path
- row count
- LLM-call count
- cache status

The Streamlit technical-details panel displays the same per-stage measurements. The benchmark script also records pipeline initialization and Python-side chart construction.

## Verification

- Focused instrumentation tests: **25 passed**.
- Full regression suite after instrumentation: **80 passed in 117.58 seconds**.
- Benchmark harness errors: **0**.
- Pipeline errors observed by the live benchmark: **3**, documented above.

## Phase 1 conclusion

The first optimization priority should be reducing or eliminating unnecessary Ollama calls, especially the second LLM call used only to phrase ordinary database results. Deterministic definitions and common KPI templates have very high potential value. Database tuning is still worth investigating for the large server-metric forecast and future raw-grain queries, but the measured SQLite timings do not justify treating the database as the main current bottleneck.

Per the project plan, no optimization is implemented in this phase. Phase 2 should begin with index inspection, representative `EXPLAIN QUERY PLAN` analysis, and measurement of server-metric aggregation candidates.
