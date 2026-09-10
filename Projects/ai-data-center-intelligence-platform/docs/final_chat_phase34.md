# Phase 34: Final Operations Copilot Conversation

The Streamlit experience now behaves as a structured operations conversation instead of a collection of isolated queries. It keeps only eight reviewed fields between turns: facility, server, original incident, related incident, metric, start date, end date, and analysis mode. It never resends the full transcript to the local model.

## Validated investigation flow

The live browser test used this sequence:

1. `What happened in Frankfurt on July 14, 2025?`
2. `Show the evidence`
3. `What happened first?`
4. `Have we seen this before?`
5. `How was the closest one fixed?`
6. `Could this happen again?`
7. `What should we inspect?`
8. `What if we upgrade the cooling system by 15%?`

The first turn resolved incident `INC-0000186`, reconstructed sourced evidence, and reported high diagnostic confidence without presenting an inferred cause as certainty. Later turns preserved the original incident while separately tracking the closest related incident. The first abnormal signal included a timestamp, event code, source table, and source ID. The final scenario correctly interpreted a cooling upgrade as a 15% reduction in cooling power.

Scenario language is metric-aware: an improvement lowers lower-is-better metrics such as PUE, latency, cooling cost, downtime, and incident count, while it raises higher-is-better metrics such as throughput and availability. Explicit increase/decrease wording always takes precedence.

Multiple questions in one message run sequentially and pass only structured context from one part to the next. A missing future year produces a counter-question; a bare follow-up year reuses the previous metric and facility. Deterministic database, forecast, scenario, risk, health, briefing, and incident paths do not need an Ollama call.

## Interface behavior

The UI uses native Streamlit chat messages, starter prompts, stable per-message chart/table keys, an evidence panel, technical timing details, a monthly briefing tab, and a governed health/risk tab. Direct control requests show that no action was executed and operator authorization is required.
