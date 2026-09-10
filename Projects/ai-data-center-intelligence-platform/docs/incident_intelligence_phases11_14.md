# Phases 11–14: Incident Intelligence and Learning

## Timeline engine

`IncidentTimelineEngine` reconstructs an incident from stored records only. It returns:

- the canonical incident start and resolution;
- daily power, network, and affected-server context with `day` precision;
- logs and alerts inside a bounded incident window with `minute` precision;
- the recorded maintenance action;
- a source table and source record identifier on every event.

The engine does not interpolate daily measurements into invented minute-level events. It labels timestamp precision so the UI can visually separate daily context from exact event timing.

## Root-cause investigation

`RootCauseInvestigationEngine` combines the timeline, same-day stored anomalies, reviewed incident knowledge, a runbook, related alerts, resolution history, and historical peers. The answer explicitly distinguishes:

- the root-cause category recorded in the historical incident;
- evidence consistent with that category;
- likely components to inspect;
- limitations on any more specific diagnosis.

It avoids definitive causal wording. Diagnostic confidence is calculated from the presence of a confirmed category, matching expected event codes, alerts, anomalies, and maintenance evidence. It is not selected by the language model.

## Similar incident retrieval

`IncidentSimilarityEngine` creates transparent profiles using components, log codes, alert types, anomaly metrics, severity, recorded cause, and facility. Fixed weights are:

| Feature | Weight |
|---|---:|
| Log codes | 25% |
| Components | 15% |
| Alert types | 15% |
| Anomaly metrics | 15% |
| Recorded root-cause category | 15% |
| Severity | 10% |
| Facility | 5% |

Set-valued features use Jaccard similarity. Categorical features use an exact-match indicator. The returned score breakdown lets an operator see why a historical incident matched. Search can start from an existing incident or from new observed signals without supplying a root cause.

## Human-controlled learning loop

`incident_reviews` keeps the AI hypothesis separate from human confirmation. The lifecycle is:

1. submit a pending AI investigation;
2. require an allow-listed reviewer role to confirm or reject it;
3. require root-cause and resolution notes for confirmation;
4. make a separate approve/reject decision for knowledge eligibility;
5. expose only confirmed and approved records as knowledge candidates.

The model never writes directly to runbooks or incident knowledge. Six example records demonstrate the full lifecycle and are marked `simulation=1`, use `simulation_reviewer`, and copy their confirmed category from the synthetic canonical history. They must not be represented as real human reviews.

## Security and integrity

- Incident, facility, server, date, and review inputs are bound query parameters.
- Investigation reads use SQLite read-only/query-only connections.
- Review writes are limited to the dedicated lifecycle table and use parameterized statements.
- Role allow-lists and state checks prevent anonymous or repeated review transitions.
- Every timeline event retains direct source provenance.

## Validation status

Source-provenance, cautious-language, similarity, and review-lifecycle tests pass in the accepted full regression suite. The protected root-cause runner additionally passed all six synthetic scenarios.

## Interview explanation

The design separates four ideas often conflated in AI demos: chronology, diagnosis, similarity, and learning. A timeline is factual reconstruction; diagnosis is a cautious evidence synthesis; similarity is a fixed mathematical score; and learning occurs only after an explicit human-controlled review state transition.
