# Verification record

This file records executed checks and outstanding acceptance tests. Runs used
Python 3.12.14. All runtime dataset results below use the explicit
SQLite rehearsal adapter; PostgreSQL is still the target warehouse.

## Executed checks

| Check | Result |
|---|---|
| Dependency consistency | `pip check`: no broken requirements |
| Python regression suite | 23 passed, 1 skipped, 26 dependency warnings in 113.40 seconds |
| Post-change core/API regression | 20 passed; 1 PostgreSQL test skipped |
| Static checks | Ruff passed; Python compileall passed |
| Docker Compose | Configuration validates |
| dbt 1.12.5 / postgres adapter 1.11.0 | Full parse passed: 25 models, 74 tests |
| n8n JSON contracts | 11 exports; graph references and approval boundary checked |
| Synthetic generation | 24 months, seed 42; linked source rows persisted |
| Pipeline | Quality → KPI → detection → investigation → forecast → recommendation completed |
| Critical data regressions | Germany Mobile conversion incident detected; tracking outage classified; conversion alerts suppressed |
| Human control | Unauthorized and unapproved calls blocked; expiry and duplicate delivery tested |
| Impact | Missing windows wait; complete windows produce an outcome; repeated verification stays single-row |
| Demo | Automated simulated approval, rollback, seven new source days, impact, outcome and lesson persisted |
| Live local API smoke check (2026-09-30) | Healthy SQLite simulation; 23 incidents and ledger rows, one SUCCESS outcome; unauthenticated ledger request returns 401; OpenAPI returns 200 |

The full test run reported dependency deprecation warnings involving pandas/NumPy
timedelta handling and Starlette's httpx test adapter. These were not failed
assertions. The installed environment is locked;
future package upgrades need these regressions rerun.

The skipped test requires a real PostgreSQL server through `TEST_DATABASE_URL`.
The HTTP smoke check used the completed SQLite dataset. It does not replace the
Docker runtime acceptance checks below. Runtime logs and exports are local outputs
and are excluded from the repository; reviewed samples are in `data/samples/`.

## Generated run evidence

Original 24-month source counts: 180,000 registered customers; 3 products;
91,980 daily traffic cohorts; 581,834 orders and matching payments; 13,931 refunds;
91,980 campaign/support/subscription/application summaries each; one checkout release;
three independent operational incident notices. The controlled simulator later adds
seven post-action days. See `data/samples/warehouse_counts.json` for the resulting
persisted table counts, not just the initial source counts.

The completed demo entry is in `data/samples/demo_ledger.json`. It records a deployment
hypothesis, ROLLBACK recommendation, explicit `automated-demo-validation` approval,
simulated rollback, +178.7% relative Germany Mobile conversion recovery, approximately
170.4%–185.7% bootstrap bounds, SUCCESS and a lesson. The target was +100% relative
conversion. These are controlled replay outputs, not proven real-world effects.

`docs/evaluation.md` is generated from hidden labels and persisted alerts. It discloses
global precision, all-scope precision, episode recall, false-positive denominator,
driver match and severity match. The scope policy was revised after identifying a
global-only incident-promotion gap. No independent-seed generalization claim is made.

The original ensemble produced 13,016 alerts, with 59.5% global and 8.7% all-scope
precision. Inspection exposed sparse-count noise. Binomial/Poisson/log-ratio count
gates reduced the final run to 844 alerts and 23 coalesced incidents. It detected all
six episodes, with 95.7% global precision (45 true-positive, 2 false-positive global
metric-day alerts) and 93.0% all-scope precision (785 true-positive, 59 false-positive
alerts). Both reports are retained. The fresh validation database reproduces the
original source records and does not copy the first run's decisions or outcomes.

`OFFLINE_DATABASE` selects the SQLite rehearsal database and defaults to
`data/generated/offline.db`. Generate it using the offline commands in the README.

## Phase-by-phase delivery status

| Phase | Delivered and checked | Remaining verification |
|---|---|---|
| 1 Foundation | Separate repository, Compose, settings, secrets, JSON logs; foundation tests | Docker engine/service startup |
| 2 Sources | 24-month linked generator, 31 warehouse tables, isolated labels | PostgreSQL insert/constraints under actual engine |
| 3 dbt | Staging, intermediate, mart/facts/dimensions/daily metrics, 74 parsed tests | Execute dbt build against PostgreSQL |
| 4 Quality | Critical quarantine and scoped tracking reconciliation; corruption tests | Real source arrival and freshness contracts |
| 5 KPI | 19 metrics, ratios of sums, distinct customers, grains and dimensions | Production-scale performance |
| 6 Detection | Seven methods, prior-only history, scopes and coalescing | Independent calibration, drift and multiple-testing control |
| 7 Investigation | Contributions, connected ratios, provider/hour/new-returning and temporal context | Causal identification is deliberately not claimed |
| 8 Forecast | Six metrics, 30 daily horizons, intervals and exposure | Empirical interval calibration |
| 9 Decisions | YAML rules, evidence IDs, memory context and targets | Rule effectiveness beyond this simulation |
| 10 API | Auth, Pydantic inputs, OpenAPI, audit and error paths | Shared-service load/security testing |
| 11 n8n | Eleven exports and import instructions; JSON contract tests | Import/activation/webhooks/scheduling in n8n |
| 12 Approval | Separate credential, pending/approved/rejected/expired transitions | SSO and authenticated operator identity |
| 13 Actions | Idempotent local simulation, approval lock and payload audit | Real external outbox/idempotency is not implemented |
| 14 Impact | Seven-day windows, control adjustment, bootstrap and outcome tests | Other action-specific impact models |
| 15 Ledger/memory | Complete view, measured lesson, past-closed incident retrieval | Larger repeated-outcome histories |
| 16 Power BI | Model, DAX, nine-page implementation specification | Manual Desktop report and visual verification |
| 17 Evaluation | Computed reports and explicit negative-day denominators | Independent validation datasets |
| 18 Demo | One-command CLI loop verified offline | Equivalent n8n/Docker runtime loop |
| 19 Polish | Dictionaries, six Mermaid diagrams, setup/run scripts and interview story | Review after outstanding runtime checks |

## Outstanding runtime checks

The validation environment had no accessible Docker engine as of 2026-09-30.
Compose configuration validation passed, but the PostgreSQL/dbt execution and n8n
runtime checks could not run. The Power BI Desktop report is also pending.

Once Docker Desktop is running Linux containers:

```powershell
docker compose up -d --build
docker compose ps
docker compose exec api python -m src.cli generate-data --months 24 --seed 42
docker compose exec api python -m src.cli transform
docker compose exec api python -m src.cli run-pipeline
docker compose exec api python -m src.cli demo
```

Then follow `n8n/README.md` for import/activation and execute the same chain there.
Use an isolated PostgreSQL test database for `TEST_DATABASE_URL`, run the marked
integration test, and inspect the Decision Ledger directly. Build and validate the
Power BI report from the provided specification. These are outstanding acceptance
checks, not already-passed steps.

## Reproducibility notes

dbt 1.12.5 parsed successfully. Pytest scratch data stays in the
workspace. The two important analytical correctness checks are weighted ratio
aggregation and distinct customer reaggregation; neither is an average/sum of
misleading preaggregated ratios or distinct counts.
