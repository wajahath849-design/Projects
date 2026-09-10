# Phase 2 SQLite Performance Optimization

## Technical summary

Phase 2 is complete. The database layer was optimized without changing canonical raw data, weakening read-only execution, or adding redundant indexes. The measured SQL benchmark improved from **41.983 ms to 0.154 ms at P50** and from **4,943.078 ms to 0.373 ms at P95**. All nine optimized queries returned the same row counts and SHA-256 result hashes as their raw-table equivalents.

The main improvement is a governed `agg_facility_yearly` table containing 66 rows: one row for each of six facilities and eleven complete calendar years from 2015 through 2025. Annual forecasting history now uses this table when it exists and safely falls back to the original raw query for an older database. Raw server/day questions continue to use the canonical `server_metrics` table.

The complete regression suite passed: **88 tests, zero failures, zero errors, and zero skipped tests in 54.563 seconds**. No Phase 2 correctness or security regression was detected.

## The 1.7M-row annual scan was the justified optimization target

Phase 1 showed that SQLite was not the main end-to-end bottleneck: local Ollama accounted for 99.03% of measured request time, and ordinary database execution had a 51.24 ms P95. The important database exception was annual server-metric forecasting, which repeatedly grouped 1,727,740 raw measurements.

The Phase 2 SQL-only suite covered nine semantic workloads:

- indexed facility/date range queries for power, network, and incidents;
- an indexed individual-server/date query;
- full facility/year aggregations for server, power, and network metrics;
- CPU and memory annual-history queries used by forecasting.

The large annual server workloads took about four to five seconds before optimization, while already-indexed detail queries were sub-millisecond to low-millisecond. This evidence supported a facility/year aggregate, not a broad index-creation exercise.

## Existing indexes already cover the important detail paths

SQLite 3.50.4 was inspected through `sqlite_master`, `PRAGMA index_list`, `PRAGMA index_info`, `sqlite_stat1`, `PRAGMA optimize(-1)`, and representative `EXPLAIN QUERY PLAN` statements.

The composite indexes proposed for investigation already existed:

| Access pattern | Existing index evidence |
|---|---|
| `server_metrics(server_id, timestamp)` | Unique auto-index created by `UNIQUE (server_id, timestamp)` |
| `power_metrics(facility_id, timestamp)` | Unique auto-index created by `UNIQUE (facility_id, timestamp)` |
| `network_metrics(facility_id, timestamp)` | Unique auto-index created by `UNIQUE (facility_id, timestamp)` |
| `uptime_incidents(facility_id, start_time)` | Explicit `idx_incidents_facility_start` |
| `uptime_incidents(server_id, start_time)` | Explicit `idx_incidents_server_start` |
| `servers(facility_id)` | Explicit `idx_servers_facility` |

For example, the server detail benchmark used:

```text
SEARCH sm USING INDEX sqlite_autoindex_server_metrics_2
(server_id=? AND timestamp>? AND timestamp<?)
```

The small `SCAN facilities` operations are appropriate because the dimension contains only six rows. Full scans or repeated server-index probes were also legitimate for queries that requested every facility and every year; the problem was the quantity of raw rows being aggregated, not a missing selective index.

No duplicate indexes were added. Before changes, planner statistics already existed and `PRAGMA optimize(-1)` returned no recommendation. After building the aggregate, `ANALYZE agg_facility_yearly` produced the statistic `66 11 1`, and `PRAGMA optimize` completed without unsafe durability settings.

## The governed annual aggregate preserves KPI calculations

`agg_facility_yearly` is rebuilt from canonical facts rather than maintained as an independent source of truth. Its grain is:

```text
facility_id + calendar year
```

It stores the required counts, averages, and sums for:

- CPU, memory, disk, and server-network utilization;
- PUE, power draw, IT load, cooling power, and cooling cost;
- bandwidth utilization, latency, packet loss, throughput, and availability;
- incident count and downtime minutes.

Each fact table is aggregated independently before the results are joined. This avoids many-to-many join multiplication between server, power, network, and incident facts. Counts are retained beside averages so a multi-year average can be weighted by its underlying observation count instead of incorrectly averaging averages.

The existing 270.21 MB database grew by only **20,480 bytes** after adding the 66-row table and its planner statistic. Canonical table counts remain unchanged:

| Canonical table | Verified rows |
|---|---:|
| `facilities` | 6 |
| `servers` | 430 |
| `server_metrics` | 1,727,740 |
| `power_metrics` | 24,108 |
| `network_metrics` | 24,108 |
| `uptime_incidents` | 1,158 |

Validation independently recomputed every stored aggregate measure from its canonical fact table. The maximum absolute difference across all measures was **0**, the aggregate had 66 unique facility/year keys, no core measurement gaps, and no foreign-key violations.

## Before-and-after benchmark results are identical and substantially faster

Each query was warmed once and measured three times on the same local database and machine. Overall percentiles contain 27 timed samples. The before run used the canonical raw-table calculation; the after run used the lowest sufficient annual grain. Result values were normalized to eight decimal places before hashing.

| Benchmark | Before P50 | After P50 | P50 speedup | Same result hash |
|---|---:|---:|---:|:---:|
| Frankfurt PUE, 2024 | 0.127 ms | 0.031 ms | 4.1× | Yes |
| Dublin latency, 2020–2025 | 1.735 ms | 0.028 ms | 62.0× | Yes |
| Individual-server CPU, 2024 | 0.199 ms | 0.158 ms | 1.3× | Yes |
| Frankfurt incidents, 2018–2024 | 0.062 ms | 0.029 ms | 2.1× | Yes |
| All server metrics by facility/year | 3,984.599 ms | 0.373 ms | 10,682.6× | Yes |
| CPU forecast history | 4,390.609 ms | 0.155 ms | 28,326.5× | Yes |
| Memory forecast history | 4,697.704 ms | 0.143 ms | 32,851.1× | Yes |
| Power metrics by facility/year | 49.624 ms | 0.371 ms | 133.8× | Yes |
| Network metrics by facility/year | 41.983 ms | 0.354 ms | 118.6× | Yes |

| Overall SQL distribution | Before | After | Improvement |
|---|---:|---:|---:|
| P50 | 41.983 ms | 0.154 ms | 272.6× |
| P95 | 4,943.078 ms | 0.373 ms | 13,252.2× |
| Maximum | 5,205.762 ms | 0.386 ms | More than 13,000× |

The Phase 1 live benchmark measured the CPU forecast stage at 3,484.128 ms. In the 30-question post-optimization pipeline check, the same CPU forecast stage took **10.598 ms**, approximately **328.8× faster**. This pipeline comparison is limited to the deterministic forecast stage; the post-check deliberately used the offline generator and is not presented as an Ollama latency comparison.

The sample count is appropriate for a local engineering comparison but too small to claim a production service-level objective. Very small sub-millisecond measurements are also sensitive to operating-system scheduling and cache state. The result-hash and query-plan evidence are therefore as important as the raw speedup ratios.

## Forecast routing uses the lowest sufficient grain

`MetricForecaster.load_history` checks whether `agg_facility_yearly` exists:

- annual facility history uses the aggregate;
- older databases without the aggregate use the original canonical query;
- raw individual-server and day-level analysis remains on `server_metrics`;
- forecasts are still refit from the current database for every request; forecast caching belongs to a later phase.

This is an explicit grain-selection decision, not a general replacement of canonical facts. It preserves detailed investigations while removing unnecessary 1.7M-row scans from annual history loading.

## Correctness, regression, and security validation passed

The clean full-suite command produced:

```text
88 passed in 54.56s
```

Coverage includes the original data-quality, cleaning, database, KPI, Power BI, RAG, SQL generation, SQL guardrail, answer validation, pipeline, memory, and forecasting tests, plus the new aggregate tests.

Validation gates all passed:

- `PRAGMA integrity_check = ok`;
- zero foreign-key violations;
- all six canonical row counts unchanged;
- 66 aggregate rows and 66 unique facility/year keys;
- zero missing core-measurement rows;
- every stored aggregate measure reconciled exactly;
- all nine before/after result hashes and row counts matched;
- 88 regression tests passed with zero failures or errors.

The first attempted full-suite run encountered one Windows permission error while pytest tried to delete a stale `.pytest_tmp` directory. It completed 87 tests with no assertion failure, but the affected test did not start. The complete suite was rerun with a fresh isolated temporary directory and cache disabled, producing the clean 88-test result above. This environmental error is not counted as a product regression.

Security behavior remains independent of performance routing:

- application connections remain SQLite read-only and `query_only`;
- SQL AST/schema validation, row limits, and timeouts remain unchanged;
- no writable query path was added to the chat application;
- aggregate rebuilds occur only through explicit maintenance/load scripts;
- raw-detail queries still pass through the existing guardrails;
- no unsafe `journal_mode`, `synchronous`, or durability pragma was introduced.

## Files added and changed

### Added

- `database/aggregates.sql` — governed aggregate definition and rebuild query.
- `scripts/build_aggregates.py` — transactional aggregate rebuild, validation, `ANALYZE`, and audit output.
- `scripts/benchmark_sql.py` — repeatable SQL timing, result hashing, and plan capture.
- `scripts/validate_phase2.py` — complete Phase 2 integrity, reconciliation, benchmark, and regression gate.
- `evaluation/sql_performance_queries.json` — nine semantic before/after SQL workloads.
- `tests/test_aggregates.py` — aggregate grain, reconciliation, forecast routing, and raw-index tests.
- `evaluation/results/sql_performance_before.json` — measured raw-query baseline.
- `evaluation/results/sql_performance_after.json` — measured optimized-query results.
- `evaluation/results/aggregate_build.json` — aggregate build audit.
- `evaluation/results/phase2_validation.json` — final validation evidence.
- `evaluation/results/phase2_pytest.xml` — clean full-suite test evidence.
- `evaluation/results/performance_phase2_offline_after.json` — 30-question deterministic post-check.

### Changed

- `scripts/load_database.py` — builds aggregates during every atomic canonical database rebuild and refreshes planner statistics.
- `src/forecasting.py` — routes annual history to the aggregate with a raw-query fallback.
- `scripts/benchmark_pipeline.py` — accepts a benchmark label for post-phase evidence.
- `docs/forecasting.md` — documents aggregate-backed annual history and fallback behavior.
- `README.md` — links this report.
- `database/datacenter.db` — contains the reproducible derived aggregate; canonical fact rows are unchanged.

## Reproduction commands

Run these commands from the project directory in Windows PowerShell:

```powershell
python scripts\build_aggregates.py
python scripts\benchmark_sql.py --variant before --repetitions 3 --warmups 1
python scripts\benchmark_sql.py --variant after --repetitions 3 --warmups 1
python -m pytest -q -p no:cacheprovider --basetemp="$env:TEMP\ai-dc-phase2-tests" --junitxml=evaluation\results\phase2_pytest.xml
python scripts\benchmark_pipeline.py --offline --label phase_2_sql_after --output evaluation\results\performance_phase2_offline_after.json
python scripts\validate_phase2.py
```

To rebuild the entire database from canonical processed CSVs, including the aggregate:

```powershell
python scripts\load_database.py
```

## What this phase establishes—and what it does not

Phase 2 establishes that the annual SQLite analytical path can avoid repeated raw scans while preserving exact results, detail access, security controls, and existing behavior. It also establishes that adding more ordinary indexes would not address the measured full-aggregation bottleneck.

It does not establish that the whole application is now fast. Phase 1 proved that local Ollama remains the dominant source of user-visible latency. The offline post-check cannot measure model cold starts, warm inference, prompt-token cost, or answer quality. Those questions belong to Phase 3 and were intentionally not addressed here.

## Interview explanation

The key design decision to explain is that an index and an aggregate solve different problems. Composite indexes already made selective server/facility date-range queries efficient. They could not eliminate the cost of calculating facility/year statistics across nearly every one of 1.7 million rows. A small, reproducible summary table solved that measured workload while the raw facts remained available for detailed questions.

You should also be able to explain:

- why query plans were inspected before changing the schema;
- why SQLite's implicit unique indexes prevented redundant index creation;
- how independent fact aggregation prevents join multiplication;
- why counts accompany averages for correct weighted rollups;
- how result hashes and raw-vs-aggregate reconciliation protect correctness;
- why read-only runtime access remains separate from explicit maintenance scripts;
- why the next bottleneck is Ollama rather than SQLite.

## Phase 2 decision

**Overall assessment: Ready to share. Phase 2 is formally complete with no detected regression.**

The next authorized step is Phase 3: measure and optimize Ollama cold/warm latency, prompt size, context size, call count, and model reuse. No Phase 3 work has started.
