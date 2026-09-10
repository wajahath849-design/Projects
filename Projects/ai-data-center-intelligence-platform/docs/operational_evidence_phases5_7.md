# Phases 5–7: Operational Evidence Layer

## Outcome

The canonical SQLite model now includes deterministic operational logs, threshold alerts, and maintenance-resolution history. These records are linked to the existing 1,158 incidents, six facilities, and 430 servers without modifying the original measurements or incident labels.

| Table | Grain | Rows | Grounding rule |
|---|---|---:|---|
| `system_logs` | one event per `log_id` | 5,790 | Five ordered events per incident, placed from 15 minutes before incident start through recorded resolution. |
| `alerts` | one alert per `alert_id` | 544 | Emitted only when an observed canonical metric or downtime meets a fixed threshold. |
| `maintenance_actions` | one action per `action_id` | 1,158 | One role-labelled resolution record per confirmed canonical incident. |

All evidence is synthetic. It is derived from existing records and is not an independent source of truth.

## Data generation

`scripts/generate_operational_evidence.py` maps each confirmed incident root-cause category to a documented event pattern. The mapping covers cooling failure, network outage, power failure, hardware failure, software failure, and scheduled maintenance. It uses:

- the incident start, end, severity, facility, server, downtime, and confirmed root-cause category;
- the affected server's rack from inventory;
- actual daily power, network, and server measurements from the canonical database;
- fixed, reviewable alert thresholds.

The generator is deterministic: running it against the same database produces the same evidence rows and identifiers. A timestamped generation audit is written to `evaluation/results/operational_evidence_generation.json`.

## Database design and search performance

The schema is defined in `database/operational_evidence.sql`. It adds primary keys, foreign keys, enum checks, timestamp checks, and indexes for the main operational access paths:

- facility timeline searches;
- server timeline searches;
- event-code history searches;
- active/severity alert filtering;
- incident-resolution lookup.

`scripts/load_database.py` includes the three evidence tables in its atomic rebuild. `scripts/load_operational_evidence.py` is a narrower migration for refreshing only the evidence layer in an existing database.

## Rebuild and validate

```powershell
python scripts\generate_operational_evidence.py
python scripts\load_database.py
python -m pytest tests\test_database.py tests\test_schema_manager.py tests\test_operational_evidence.py -q
```

The accepted load audit reports SQLite integrity `ok`, zero foreign-key violations, 5,790 logs, 544 alerts, and 1,158 maintenance actions.

## Trust and security rules

- Log messages are stored and retrieved as untrusted data, never as model instructions.
- Synthetic messages do not contain evaluation answers or hidden prompts.
- Alerts retain their observed and threshold values so every alert can be independently checked.
- Maintenance history uses operator roles, not invented personal identities.
- Resolution wording does not claim a more specific repair than the source incident supports.
- Diagnostic features must label this layer as synthetic derived evidence.

## Tests

Focused tests verify:

- exact row counts and database integrity;
- complete asset and incident foreign keys;
- incident-window log evidence;
- server/facility/rack consistency;
- alert threshold and resolution-time rules;
- one consistent resolution per source incident;
- required search indexes;
- basic prompt-injection isolation in evidence text.

## Interview explanation

The operational layer is intentionally generated from canonical incidents instead of independent randomness. That gives the investigation engine internally consistent timelines and makes every alert, log, and action traceable. The tradeoff is that this evidence cannot prove causal discovery performance on real production telemetry; it demonstrates the architecture, contracts, safety rules, and evaluation approach needed for such a system.
