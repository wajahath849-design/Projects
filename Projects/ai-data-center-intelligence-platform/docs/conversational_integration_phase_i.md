# Phase I — Conversational Integration

The chat router now recognizes real-time status/metrics/anomalies/incidents,
specialist investigation, cost, carbon, efficiency scenarios, incident impact,
correlation, intervention, and causal-evidence requests. Users may phrase these
requests naturally; deterministic engines still perform every numerical
calculation.

Conversation state stores only compact structured fields: facility/server/
incident scope, dates, metric, simulation session, live or historical mode,
cost/carbon scenario, intervention, comparison scope, selected causal method,
and chart state. Full chat history is not forwarded to analytics or local AI.
Missing dates, metrics, facilities, or scenario percentages trigger a concise
counter-question. Multiple questions are split, answered independently, and
carry the structured context forward.
