# Phases 31–33: Root-Cause Evaluation, Security, and Human Control

## Protected root-cause evaluation

The protected evaluation contains six deterministic synthetic scenarios: cooling failure, network outage, power disturbance, disk degradation, server overheating, and application overload. Production investigation, retrieval, similarity, and recommendation objects are constructed before the evaluator reads the private truth file. Only an incident ID crosses into production logic.

The accepted run in `evaluation/results/root_cause_phase31.json` passed 6/6 scenarios. Incident detection, component identification, evidence retrieval, similar-incident retrieval, root-cause classification, and recommendation relevance each scored 6/6. This proves correctness for the protected synthetic cases; it is not a real-world causal-accuracy claim.

## Untrusted operational text

Questions, log messages, retrieved knowledge, and database rows are serialized inside explicit JSON data boundaries. Both SQL and answer prompts instruct the model to treat bounded content as evidence only and never as commands. Evaluation content is excluded from the production retrieval corpus.

SQL is independently parsed and allow-listed after generation. The executor accepts one read-only query, uses a read-only SQLite connection, applies row and time limits, and blocks writes, multi-statements, PRAGMA, ATTACH, and unknown schema.

## Human authorization boundary

The copilot does not restart servers, change cooling controls, alter firewall or network settings, delete data, or perform other infrastructure actions. Direct action requests return an approval-required response before SQL, retrieval, or model execution. Historical and explanatory questions about those actions remain available.

Recommendations and what-if scenarios are advisory. Confirmed incident reviews require an approved reviewer role before becoming similarity candidates. The application makes synthetic evidence, forecast uncertainty, and human authorization visible in the interface.

## Verification

- `tests/test_operational_security.py` covers prompt-boundary serialization and the direct-action gate.
- `tests/test_root_cause_evaluation_isolation.py` checks protected truth isolation and all six scenarios.
- `evaluation/results/offline_baseline.json` records 10/10 SQL security cases.
- `evaluation/results/advanced_release_validation.json` consolidates final release evidence.
