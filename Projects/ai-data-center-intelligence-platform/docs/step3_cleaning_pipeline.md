# Step 3 — Reproducible Cleaning Pipeline

## 1. What

Step 3 implements a deterministic pipeline that transforms the immutable CSVs in `data/raw` into independently generated clean files under `data/cleaned_generated`.

The pipeline:

1. removes exact duplicate fact measurements;
2. normalizes controlled status labels;
3. converts values outside documented domains to missing;
4. imputes missing values within each server or facility time series;
5. applies canonical numeric precision;
6. validates output structure and quality;
7. compares generated output with the supplied `data/processed` baseline.

It does not overwrite either supplied dataset.

## 2. Why

A clean dataset is trustworthy only when its transformations are reproducible and auditable. Copying the supplied processed files would demonstrate no ETL reasoning. This pipeline starts from raw evidence, records every repair count, and tests the result before later database or Power BI work consumes it.

## 3. Concepts

- **Idempotent transformation:** rerunning the same rules on the same input produces the same data values.
- **Deterministic deduplication:** the first exact occurrence is retained according to stable source order.
- **Domain validation:** impossible or project-invalid values are marked missing before imputation.
- **Entity-aware interpolation:** a missing daily value is estimated only from the same server or facility's time series.
- **Fallback hierarchy:** if interpolation cannot resolve an edge case, use the entity median, then the global column median.
- **Data lineage:** the audit file records input, output, rule version, repair counts, and baseline comparison.
- **Golden baseline:** the supplied processed dataset is used for comparison, not as a source of replacement values.

## 4. Files created or changed

- `config/cleaning_rules.yaml`: versioned declarative cleaning contract.
- `scripts/clean_data.py`: complete cleaning and baseline-comparison implementation.
- `tests/test_cleaning_pipeline.py`: eight automated pipeline tests.
- `docs/step3_cleaning_audit.json`: machine-readable execution audit.
- `docs/step3_cleaning_pipeline.md`: this explanation and verification guide.
- `data/cleaned_generated/`: generated output location; CSVs are ignored by Git.
- `.gitignore`, `pytest.ini`, and `README.md`: runtime and project-stage updates.

No raw or supplied processed CSV was edited.

## 5. Cleaning rules

### Deduplication

| Table | Key/grain | Removed |
|---|---|---:|
| server_metrics | metric_id + server_id + timestamp | 314 |
| power_metrics | metric_id + facility_id + timestamp | 15 |
| network_metrics | metric_id + facility_id + timestamp | 13 |

The duplicates are exact copies, so keeping the first record loses no distinct information.

### Category normalization

- Six server statuses are trimmed and lowercased from `ACTIVE` to `active`.
- Twenty-four incident statuses are trimmed/lowercased and mapped from `done`, `RESOLVED`, or `Closed` to `resolved`.
- Unknown values cause the pipeline to fail rather than being guessed.

### Invalid values

The following values are marked missing before imputation:

- 343 CPU-utilization values outside 0–100%.
- 343 memory-utilization values outside 0–100%.
- 25 PUE values outside 1.0–2.0 for this project dataset.
- 25 packet-loss values outside 0–5% for this project dataset.

The PUE and packet-loss thresholds are project-contract assumptions, not universal operational laws.

### Imputation

For each measure, the data is sorted by entity and date. Linear interpolation uses observations belonging only to the same server or facility. If an edge gap cannot be interpolated, the pipeline uses that entity's median and finally the global median.

This method was chosen because it:

- respects entity boundaries;
- preserves local time trends better than global mean replacement;
- is deterministic and explainable;
- does not treat unknown values as zero.

Its limitation is that it smooths local variation and does not reconstruct the original hidden random observation.

### Precision

Most measures use two decimal places. PUE and packet loss use three, and network availability uses four, matching the canonical source precision.

## 6. Output verification

Generated row counts are:

| Table | Generated rows | Supplied processed rows | Match |
|---|---:|---:|---|
| facilities | 6 | 6 | yes |
| servers | 430 | 430 | yes |
| server_metrics | 1,727,740 | 1,727,740 | yes |
| power_metrics | 24,108 | 24,108 | yes |
| network_metrics | 24,108 | 24,108 | yes |
| uptime_incidents | 1,158 | 1,158 | yes |

Verification also confirms:

- identical column names and order;
- no missing values;
- unique primary and natural-grain keys;
- canonical status values;
- valid percentage, PUE, and packet-loss ranges;
- complete foreign-key coverage;
- successful CSV write/read round trip.

## 7. Comparison with the supplied processed baseline

Every cell unaffected by injected corruption matches the supplied baseline exactly. Differences occur only where the raw value was missing or invalid and therefore could not be recovered exactly.

| Table/column | Generated vs baseline mismatches | Match rate | MAE on mismatches |
|---|---:|---:|---:|
| server_metrics.cpu_utilization_pct | 685 | 99.960353% | 5.471343 percentage points |
| server_metrics.memory_utilization_pct | 696 | 99.959716% | 7.744756 percentage points |
| server_metrics.disk_utilization_pct | 358 | 99.979279% | 6.818911 percentage points |
| server_metrics.network_utilization_pct | 320 | 99.981479% | 7.035406 percentage points |
| power_metrics.cooling_power_kw | 22 | 99.908744% | 78.637727 kW |
| power_metrics.pue | 53 | 99.780156% | 0.013642 |
| power_metrics.cooling_cost | 18 | 99.925336% | 237.326667 currency-equivalent units |
| network_metrics.latency_ms | 36 | 99.850672% | 1.153056 ms |
| network_metrics.packet_loss_pct | 56 | 99.767712% | 0.028750 percentage points |
| network_metrics.throughput_mbps | 24 | 99.900448% | 396.276667 Mbps |

Why exact equality is neither possible nor claimed: the package was created by generating clean observations and then replacing selected raw cells with nulls or artificial outliers. Once replaced, the original observation is absent from raw data. The supplied processed dataset retains those hidden original values; an independent cleaner can estimate them but cannot logically recover them.

Four repaired PUE cells and one repaired packet-loss cell happen to equal the baseline after rounding, explaining why mismatch counts are slightly below affected-cell counts.

## 8. Code

The full implementation is in `scripts/clean_data.py`; it contains no placeholder logic. Rules are intentionally separate in `config/cleaning_rules.yaml` so thresholds and mappings are reviewable without changing Python code.

## 9. Commands

From the project root with the Python 3.12 environment activated:

```powershell
python scripts\clean_data.py
python -m pytest tests\test_cleaning_pipeline.py -q
python -m pytest -q
```

To use different locations:

```powershell
python scripts\clean_data.py `
  --raw-dir data\raw `
  --output-dir data\cleaned_generated `
  --baseline-dir data\processed `
  --rules config\cleaning_rules.yaml `
  --audit docs\step3_cleaning_audit.json
```

## 10. Expected output

```text
Wrote 6 cleaned CSVs to data\cleaned_generated
Wrote audit report to docs\step3_cleaning_audit.json
........
8 passed
```

The full suite should report 15 passing tests: seven Step 2 profiling tests plus eight Step 3 cleaning tests.

## 11. Verification checklist

- [x] Raw inputs remain unchanged.
- [x] Supplied processed baseline remains unchanged.
- [x] Evaluation ground truth is never read.
- [x] Cleaning rules are versioned outside the code.
- [x] Exact duplicates are removed deterministically.
- [x] Status values are canonical.
- [x] Invalid values are flagged before imputation.
- [x] Missing values are imputed within entity time series.
- [x] Generated data has no nulls or duplicate grains.
- [x] Generated schemas and row counts match the supplied baseline.
- [x] Unaffected values match the baseline exactly.
- [x] Non-recoverable cell differences are measured and disclosed.
- [x] Eight Step 3 tests pass.

## 12. Common errors

**`ModuleNotFoundError` for pandas or yaml:** activate `.venv`, then run `python -m pip install -r requirements.txt`.

**Unexpected categorical value:** inspect the value and decide whether it has a valid canonical mapping. Do not add a mapping merely to silence the failure.

**Generated CSV is locked:** close Excel or another application holding the file and rerun.

**Memory error:** close memory-heavy programs. The transparent pandas implementation loads the 1.7M-row file in memory. At larger scale, use partitioned processing, DuckDB, Polars streaming, or a warehouse transformation.

**Baseline comparison reports differences in unaffected fields:** stop. This indicates ordering, schema, rounding, or unintended-transformation drift and must be fixed before database loading.

## 13. Interview preparation

**Why not use zero for missing metrics?** Zero is a real observation. Replacing unknown data with zero creates systematic downward bias.

**Why interpolate by entity?** Measurements from another server or facility are not interchangeable. Entity grouping prevents cross-asset leakage.

**Why use a median fallback?** Median is robust to extreme values and provides a deterministic fallback when interpolation has no valid boundary observation.

**Why keep rules in YAML?** It separates policy from execution, makes reviews easier, and allows tests and future adapters to reference the same contract.

**What does idempotence mean here?** Given identical raw inputs and rule version, the cleaner produces identical data values. The audit timestamp changes, but the cleaned dataset does not.

**Why does generated output not exactly equal the supplied processed dataset?** Missing and corrupted raw cells have lost their original information. The baseline contains the pre-corruption values, while the independent pipeline estimates them transparently.

**How would this change at scale?** Use partitioned transformations in a warehouse or distributed engine, persist quality metrics, enforce schema contracts at ingestion, and use incremental checks rather than loading all history into memory.

**How do you prevent silent cleaning errors?** Fail on unknown categories, test keys and ranges, compare all unaffected cells to a golden baseline, and retain an audit of every rule and affected count.

## Step boundary

Step 3 is complete. Canonical database-model decisions and SQLite implementation remain outside this step.
