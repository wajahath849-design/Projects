# Phases 19–22: Advanced Chat, Structured Context, Evidence, and Confidence

## Deterministic chat modes

The copilot router recognizes:

- definition, historical analytics, SQL analytics, comparison, and forecast;
- scenario analysis;
- anomaly, incident, and root-cause investigation;
- log search and similar-incident search;
- maintenance recommendation;
- predictive maintenance;
- facility health assessment;
- decision support.

Advanced operational routes are deterministic and do not require an LLM call. Existing Text-to-SQL remains the fallback for flexible historical analytics.

## Structured conversation state

The session carries only eight fields: facilities, server, original incident, related incident, metric, start date, end date, and analysis mode. It does not resend the full conversation transcript to Ollama.

Explicit new facilities or assets replace stale entity context. Follow-ups such as “Show me the logs,” “Any similar incident?”, “How was it fixed?”, and “Could this happen again?” reuse the selected incident and server. An unrelated explicit question such as “What is PUE?” is not hijacked by old incident context.

When facility/date/server context matches more than one incident, the copilot asks the user to select from sourced incident identifiers. It does not guess.

## Evidence panel contract

Diagnostic results expose structured expandable evidence:

- metrics used;
- logs used;
- alerts used;
- incidents used;
- runbooks used;
- similar incidents;
- maintenance history;
- stored anomalies;
- generated SQL when relevant;
- investigation time window;
- confidence score and breakdown.

Every timeline item retains a source table and record identifier. Scenarios separately expose their baseline, assumption, and calculated results.

## Diagnostic confidence

Confidence is calculated by `DiagnosticConfidenceEngine`, never written by the LLM. The fixed nine-point evidence scale assigns:

| Evidence | Maximum points |
|---|---:|
| Recorded incident category | 2 |
| Correlated metrics/anomalies | 2 |
| Matching log codes | 2 |
| Alerts | 1 |
| Similar incidents | 1 |
| Confirmed maintenance history | 1 |

Scores 0–3 are Low, 4–6 Moderate, and 7–9 High. Missing evidence remains visible in the breakdown; confidence reflects coverage and corroboration, not certainty of a specific causal mechanism.

## Security behavior

Database-changing language is blocked before advanced routing. All database lookups use bound parameters or fixed generated templates. Operational data is never treated as prompt instructions, and advanced deterministic modes use zero LLM calls.

## Validation status

Mode routing, compact context, stale-context isolation, confidence arithmetic, incident follow-ups, evidence panels, zero-LLM scenario/decision paths, and unsafe-input blocking are covered by the accepted full regression suite. The final eight-turn flow is documented in `docs/final_chat_phase34.md`.
