# Step 5 — SQLite Analytical Database

## What and why

Step 5 creates a constrained, indexed SQLite database from the verified supplied processed dataset. SQLite provides a portable analytical engine for later AI SQL execution and a reproducible reference for Power BI KPI validation.

The database is generated atomically: data loads into `datacenter.db.building`, passes integrity checks, and only then replaces `datacenter.db`. A failed build cannot leave a half-loaded production file.

## Files

- `database/schema.sql`: six canonical tables, keys, constraints, and indexes.
- `database/views.sql`: five genuinely useful analytical views.
- `database/datacenter.db`: generated database, intentionally ignored by Git.
- `scripts/load_database.py`: chunked, transactional loader and validator.
- `tests/test_database.py`: six database tests.
- `docs/step5_database_audit.json`: load audit.

## Physical design

All primary IDs use `TEXT` and domain measures use `REAL` or `INTEGER`. ISO dates use `TEXT`, which preserves lexical time order in SQLite. `WITHOUT ROWID` avoids redundant internal row identifiers for tables already keyed by stable text IDs.

Foreign keys enforce facility and server relationships. CHECK constraints enforce allowed statuses, severities, dates, nonnegative measures, percentage domains, valid incident chronology, and total power not below IT load.

## Indexes

SQLite automatically indexes primary and unique keys. Added indexes support:

- dimension-to-fact joins;
- date filtering on each large fact;
- facility/server incident timelines;
- severity and root-cause exploration;
- active-server filtering by facility.

Indexes are intentionally not added to every numeric measure because analytical scans would gain little while database size and load time would increase.

## Views

- `vw_facility_daily_performance`: aligned power and network facts by facility/date.
- `vw_monthly_energy_summary`: reusable monthly energy/PUE aggregation.
- `vw_server_utilization`: enriched server measurements.
- `vw_incident_summary`: enriched reliability detail.
- `vw_facility_reliability`: facility-level incident and downtime-per-server summary.

## Commands

```powershell
python scripts\load_database.py
python -m pytest tests\test_database.py -q
```

Expected: integrity `ok`, zero foreign-key violations, canonical row counts, five views, nine explicit indexes, and six passing tests.

## Verification checklist

- [x] Proper primary and foreign keys.
- [x] Natural-grain UNIQUE constraints.
- [x] Domain and chronology CHECK constraints.
- [x] Chunked load of 1.7M server rows.
- [x] Atomic database replacement.
- [x] Integrity and foreign-key checks pass.
- [x] Row counts match the manifest.
- [x] Read-only URI blocks writes.
- [x] Five analytical views validated.

## Common errors

- Locked database: close tools holding `datacenter.db` and rerun.
- Constraint failure: rerun Step 3/4 validation and inspect the named field; do not disable constraints.
- Disk-space failure: retain space for both the existing database and `.building` replacement.

## Interview preparation

**Why SQLite?** It is portable, supports analytical SQL and constraints, and is sufficient for a single-user portfolio system.

**Why indexes?** They reduce lookup and filtering work, especially for joins and dates, at the cost of storage and slower writes.

**Why atomic replacement?** Consumers see either the old valid database or the new valid database, never a partial build.

**Production migration?** Move DDL and loads to PostgreSQL, add roles/read replicas, partition large facts, and use managed migrations.
