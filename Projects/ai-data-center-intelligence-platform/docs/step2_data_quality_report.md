# Step 2 — Raw Data Profiling and Data Quality Report

## 1. What

This step profiles the six immutable files under `data/raw` and establishes whether they are safe for analytics before cleaning. It measures schema, grain, data types, completeness, duplicate keys and rows, validity, categorical consistency, temporal coverage, cross-field consistency, and referential integrity.

The raw data is **not analytics-ready**. It contains small, controlled defects across the fact tables and categorical status fields. The defects are suitable for demonstrating a realistic cleaning pipeline, and the underlying entity relationships and daily time series are structurally complete.

## 2. Why

Power BI and conversational analytics can produce plausible but incorrect results when duplicates inflate totals, missing values change denominators, invalid percentages distort averages, or inconsistent labels split categories. Profiling converts those risks into explicit, testable cleaning requirements.

## 3. Concepts

- **Grain:** what one row represents. The three metric tables have a daily entity grain: server plus date or facility plus date.
- **Completeness:** whether required values are populated.
- **Uniqueness:** whether primary keys and business-grain keys identify one row only.
- **Validity:** whether values conform to types, formats, and defensible business ranges.
- **Consistency:** whether equivalent categories and related fields agree.
- **Referential integrity:** whether every child identifier resolves to its parent entity.
- **Temporal coverage:** whether every expected entity-date combination is present.
- **Outlier:** a value outside a defined domain or robust expectation. An outlier is flagged for investigation; it is not automatically deleted.

## 4. Dataset and grain summary

| Table | Raw rows | Intended grain | Primary-key candidate | Result |
|---|---:|---|---|---|
| facilities | 6 | facility | facility_id | clean in tested dimensions |
| servers | 430 | server | server_id | six inconsistent status labels |
| server_metrics | 1,728,054 | server per day | metric_id | missing values, 314 duplicates, 686 invalid percentage cells |
| power_metrics | 24,123 | facility per day | metric_id | missing values, 15 duplicates, 25 invalid PUE values |
| network_metrics | 24,121 | facility per day | metric_id | missing values, 13 duplicates, 25 invalid packet-loss values |
| uptime_incidents | 1,158 | incident | incident_id | 24 inconsistent status labels |

## 5. Checks performed

The profiler performed:

1. Row, column, file-size, and inferred-type inspection.
2. Null counts and rates by column.
3. Exact-row, primary-key, and natural-grain duplicate checks.
4. Date parsing and minimum/maximum date validation.
5. Numeric summaries including quartiles, p99, minimum, maximum, and mean.
6. Explicit domain checks for percentages, PUE, packet loss, positive capacity/power/cost, and availability.
7. Controlled-vocabulary inspection for low-cardinality categorical fields.
8. Parent-child key coverage for all six modeled relationships.
9. Daily coverage across all 4,018 days from 2015-01-01 through 2025-12-31.
10. Cross-field checks for incident duration, chronological order, power versus IT load, and build versus commission year.
11. Year-by-year distribution of missing cells, duplicates, and invalid-range cells.

## 6. Findings

### DQ-001 — Duplicate fact measurements

**Severity: High. Confidence: High.**

| Table | Extra duplicate rows | Affected rows | Extra-row rate |
|---|---:|---:|---:|
| server_metrics | 314 | 628 | 0.018171% |
| power_metrics | 15 | 30 | 0.062181% |
| network_metrics | 13 | 26 | 0.053895% |

The duplicates are exact rows and violate both `metric_id` uniqueness and the corresponding entity-date grain. If loaded unchanged, they can overstate sums and weighted results and prevent creation of database primary keys.

**Step 3 requirement:** deterministically retain one exact row and assert uniqueness on both the ID and natural grain afterward.

### DQ-002 — Missing analytical measures

**Severity: High. Confidence: High.**

| Table | Column | Missing cells |
|---|---|---:|
| server_metrics | cpu_utilization_pct | 342 |
| server_metrics | memory_utilization_pct | 353 |
| server_metrics | disk_utilization_pct | 358 |
| server_metrics | network_utilization_pct | 320 |
| power_metrics | cooling_power_kw | 22 |
| power_metrics | pue | 32 |
| power_metrics | cooling_cost | 18 |
| network_metrics | latency_ms | 36 |
| network_metrics | packet_loss_pct | 32 |
| network_metrics | throughput_mbps | 24 |

Totals are 1,373 missing server-measure cells, 72 power-measure cells, and 92 network-measure cells. SQL averages ignore nulls, so different KPIs could silently use different denominators.

**Step 3 requirement:** use a documented, group-aware imputation rule appropriate to daily time series, preserve identifiers and timestamps, and log every repair. Do not replace all nulls with zero.

### DQ-003 — Invalid CPU and memory percentages

**Severity: High. Confidence: High.**

- CPU utilization above 100%: 343 cells; raw maximum 174.64%.
- Memory utilization above 100%: 343 cells; raw maximum 174.84%.
- Disk and network utilization values remain within 0–100%.

These 686 values can bias capacity, hotspot, and facility-comparison analyses upward.

**Step 3 requirement:** flag and repair these values with a reproducible robust method. Capping is simple but can create artificial mass at 100%; group-aware replacement is preferable if validated against the supplied processed baseline.

### DQ-004 — Invalid PUE and packet-loss extremes

**Severity: High. Confidence: High.**

- PUE outside the project-specific 1.0–2.0 range: 25 rows; raw maximum 2.998.
- Packet loss above the project-specific 5% range: 25 rows; raw maximum 21.939%.

The thresholds are explicit assumptions for this synthetic canonical dataset, not universal industry laws. Comparison with the supplied processed baseline confirms exactly 25 repaired values in each field.

**Step 3 requirement:** retain the thresholds in configuration, flag the records, apply an auditable repair, and compare output values with the processed baseline.

### DQ-005 — Inconsistent categorical status labels

**Severity: Medium. Confidence: High.**

- Servers: six `ACTIVE` values conflict with lowercase `active`.
- Incidents: 24 rows use `done`, `RESOLVED`, or `Closed` instead of canonical `resolved`.

Without normalization, dashboard slicers and SQL groupings treat equivalent states as separate categories.

**Step 3 requirement:** trim and lowercase labels, then map known completion synonyms to `resolved`. Reject or quarantine unknown labels rather than guessing.

### DQ-006 — Structural integrity is sound

**Severity: Low/positive control. Confidence: High.**

- Zero missing foreign-key values across the six tested relationships.
- Zero orphan foreign-key values.
- Zero invalid dates detected.
- Zero incidents ending before they start.
- Zero incident-duration mismatches.
- Zero power rows where total power is below IT load.
- Zero facilities commissioned before their build year.
- All 430 servers have 4,018 unique daily measurements after deduplication.
- All six facilities have 4,018 unique power and network dates after deduplication.

These checks show that cleaning can remain narrowly focused; rebuilding relationships or synthesizing missing calendar rows is unnecessary.

## 7. Temporal and distribution observations

Missing cells, duplicates, and invalid values occur throughout 2015–2025. No single year explains the problem:

- Server missing cells range from 115 to 136 per year.
- Server duplicate extras range from 20 to 39 per year.
- Server invalid-range cells range from 53 to 80 per year.
- Power and network defects are similarly dispersed in small counts.

This pattern is consistent with controlled random injection rather than a one-time source migration or failed historical partition. There are no missing daily entity-date combinations once duplicates are removed.

## 8. Comparison with supplied issue metadata

The independently measured counts reconcile with `data_quality_issues.json`:

- 314, 15, and 13 duplicate extras across the three fact tables.
- 1,373, 72, and 92 missing measure cells.
- 686 invalid CPU/memory cells, 25 invalid PUE values, and 25 invalid packet-loss values.
- Six server and 24 incident status inconsistencies.

This reconciliation increases confidence in the package design, but Step 3 must still independently reproduce the supplied processed files rather than copying their transformations blindly.

## 9. Files created or changed

- `scripts/profile_data.py`: complete, read-only profiler.
- `docs/step2_data_quality_profile.json`: machine-readable measured evidence.
- `docs/step2_data_quality_report.md`: interpreted report and teaching material.
- `tests/test_data_quality.py`: seven regression tests.
- `notebooks/README.md`: records why no unexecuted notebook was presented as validated evidence.
- `README.md`: current project-stage status.

No raw or processed CSV was changed.

## 10. Commands

After installing and activating the Python 3.12 environment described in Step 1:

```powershell
cd "C:\Users\admin\Downloads\AI_Image_Classification_Final_Project_Import_Fixed\ai-data-center-intelligence"
python scripts\profile_data.py
python -m pytest tests\test_data_quality.py -q
```

Optional inspection commands:

```powershell
Get-Content docs\step2_data_quality_report.md
Get-Content docs\step2_data_quality_profile.json -TotalCount 40
```

## 11. Expected output

```text
Wrote docs\step2_data_quality_profile.json
.......
7 passed
```

The exact runtime varies by machine. On the verified local runtime, the seven tests completed in approximately 12 seconds; this is a local observation, not a production performance claim.

## 12. Verification checklist

- [x] Raw files treated as immutable inputs.
- [x] Evaluation ground truth excluded from all profiling paths.
- [x] All six datasets profiled.
- [x] Grain and key candidates tested.
- [x] Missing values measured by column.
- [x] Exact, ID, and natural-grain duplicates measured.
- [x] Domain and date validity tested.
- [x] Status inconsistencies measured.
- [x] Referential integrity tested.
- [x] Cross-field consistency tested.
- [x] Daily time coverage tested.
- [x] Defects segmented by year.
- [x] Results reconciled with, but not derived from, supplied issue metadata.
- [x] Seven automated tests pass.
- [x] No cleaning implemented and no source data modified.

## 13. Common errors and fixes

**`python` is not recognized or the launcher reports no installed Python.** Install 64-bit Python 3.12, enable the launcher, reopen PowerShell, and recreate `.venv` using the Step 1 commands.

**`ModuleNotFoundError: pandas`.** Activate `.venv` and run `python -m pip install -r requirements.txt`.

**File-not-found errors.** Run commands from the project root or pass `--raw-dir` explicitly.

**Memory pressure while profiling.** Close Power BI and other memory-heavy applications. The current profiler loads the roughly 101 MB server CSV into memory to make exact cross-row duplicate and grain checks transparent. At larger scale, replace this with chunked hashing or database-backed profiling.

**A future dataset fails the hard-coded PUE or packet-loss rule.** Treat these as dataset-contract assumptions. Review units and operational expectations before changing thresholds; do not silently weaken tests.

## 14. Interview preparation

**What is the difference between a primary key and grain?** A primary key is the technical identifier. Grain describes the business meaning of one row. Both must be unique; a new ID does not make two measurements for the same server and date logically valid.

**Why are duplicates dangerous?** They inflate aggregates, bias averages when duplication is uneven, and can break constrained database loads.

**Why not fill missing utilization with zero?** Zero means measured inactivity, while null means unknown. Conflating them biases utilization downward.

**How did you detect outliers?** I used explicit physical or project-contract ranges for percentages, PUE, and packet loss, then reconciled the flagged counts with the trusted baseline. For less constrained measures, Step 3 can use robust statistics such as IQR or MAD.

**Why segment issues by year?** It distinguishes random low-rate defects from a source change, backfill, or broken partition concentrated in a specific period.

**What did referential-integrity testing prove?** Every server and fact row references an existing parent facility or server, so joins will not silently lose records.

**Would this profiler scale to billions of rows?** No. At production scale I would push checks into the warehouse, process partitions incrementally, use data-quality tooling, and store only compact metrics and samples locally.

**Why preserve the raw files?** Immutable raw evidence makes transformations reproducible, auditable, and reversible.

## Step boundary

Step 2 is complete. Cleaning logic, cleaned-output generation, and comparison against the supplied processed dataset belong to Step 3 and have not been implemented here.
