# Phases 8–9: Incident Knowledge and Runbook RAG

## Outcome

The production knowledge base now contains three reviewed operational collections:

- six incident-pattern records covering every canonical root-cause category;
- six safety-aware operator runbooks;
- eighteen operational event-code definitions.

These complement the existing schema, KPI, glossary, forecast, and verified SQL collections. No evaluation files or answers are indexed.

## Sources and provenance

| Source | Collection | Purpose |
|---|---|---|
| `knowledge/incident_knowledge.yaml` | `incident_knowledge` | Symptoms, components, codes, metrics, diagnostic hypotheses, checks, historical resolution patterns, and explicit limitations. |
| `knowledge/runbooks.yaml` | `runbooks` | Ordered investigation and escalation workflows with human-authorization boundaries. |
| `knowledge/error_codes.yaml` | `error_codes` | Stable meaning and recommended check for each important generated event code. |

Every retrieved chunk carries its collection, type, source, and domain identifier. Source paths are resolved inside the project root, required to exist, and rejected when any path segment is `evaluation`.

## Routed retrieval

`Retriever.retrieve_for_sql()` only searches semantic, forecast, and verified-SQL collections, then adds exact schema chunks required by domain hints. Runbook text therefore cannot accidentally enter SQL generation.

`Retriever.retrieve_for_investigation()` searches only incident knowledge, runbooks, and error-code documentation. This keeps investigation context compact and avoids unrelated KPI or schema chunks.

The generic retrieval method also accepts an explicit collection set. An unknown or forbidden collection produces no results rather than silently falling back to the full corpus.

## Safety and trust

- Knowledge is version-controlled and reviewed; the model cannot write directly to it.
- Likely causes are phrased as areas to investigate, not confirmed diagnosis.
- Runbooks state authorization and safety boundaries for physical, network, electrical, hardware, and software changes.
- Human confirmation is required before a specific cause or repair becomes trusted history.
- Operational evidence and knowledge are synthetic portfolio artifacts and are labelled accordingly.

## Verification

Focused retrieval tests verify exact error-code lookup, cooling-incident retrieval, collection isolation, SQL/runbook separation, and evaluation exclusion. The accepted focused suite completed with 15 passing tests.

## Interview explanation

The important design choice is collection-aware retrieval. SQL generation, terminology lookup, and incident investigation have different evidence needs and risk profiles. Routing them to reviewed collections improves relevance, reduces prompt length, and prevents operational instructions from contaminating the SQL path.
