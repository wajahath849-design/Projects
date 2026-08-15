# Step 1 — Dataset Inspection and Environment Setup

## Outcome

The supplied ZIP was inspected before project setup. Its manifest, schemas, row counts, date ranges, missing-value counts, candidate keys, and tested foreign-key relationships were checked against the actual CSV files. The dataset is synthetic, reproducible (seed 42), and spans 2015-01-01 through 2025-12-31.

The evaluation answer file is stored only at `evaluation/private/ground_truth_anomalies.json`. That directory is ignored by Git and must be excluded from every production, prompt-building, retrieval, and answer-generation path.

## Actual ZIP structure

```text
datacenter_project_dataset_2015_2025_v2.zip
├── README_DATASET.md
├── raw/
│   ├── facilities.csv
│   ├── servers.csv
│   ├── server_metrics.csv
│   ├── power_metrics.csv
│   ├── network_metrics.csv
│   └── uptime_incidents.csv
├── processed/
│   └── the same six canonical CSVs
├── metadata/
│   ├── metric_definitions.yaml
│   ├── business_glossary.yaml
│   ├── canonical_data_contract.json
│   ├── dataset_manifest.json
│   └── data_quality_issues.json
├── adapters/
│   ├── schema_mapping_template.yaml
│   └── default_aliases.json
└── evaluation/
    └── ground_truth_anomalies.json
```

## Measured dataset inventory

| Dataset | Canonical grain | Raw rows | Processed rows | Raw size | Processed size | Operational date range |
|---|---|---:|---:|---:|---:|---|
| facilities | one row per facility | 6 | 6 | 581 B | 581 B | commission dates 2009-08-18 to 2014-05-06 |
| servers | one row per server | 430 | 430 | 30,481 B | 30,481 B | install dates 2010-01-07 to 2014-12-17 |
| server_metrics | one daily measurement per server | 1,728,054 | 1,727,740 | 101,247,033 B | 101,234,679 B | 2015-01-01 to 2025-12-31 |
| power_metrics | one daily measurement per facility | 24,123 | 24,108 | 1,691,742 B | 1,691,108 B | 2015-01-01 to 2025-12-31 |
| network_metrics | one daily measurement per facility | 24,121 | 24,108 | 1,586,549 B | 1,586,141 B | 2015-01-01 to 2025-12-31 |
| uptime_incidents | one row per incident | 1,158 | 1,158 | 117,256 B | 117,308 B | 2015-01-05 to 2025-12-08 |

The metric-table counts are internally consistent: 430 servers × 4,018 days = 1,727,740 processed server measurements, and 6 facilities × 4,018 days = 24,108 processed power and network measurements.

## Columns and candidate keys

- `facilities`: facility_id (PK); facility_name, city, country, region, capacity_mw, rack_capacity, build_year, commission_date.
- `servers`: server_id (PK); facility_id (FK), rack_id, server_type, cpu_cores, memory_gb, install_date, status.
- `server_metrics`: metric_id (PK); server_id (FK), timestamp, cpu_utilization_pct, memory_utilization_pct, disk_utilization_pct, network_utilization_pct. A natural uniqueness check should also cover `(server_id, timestamp)`.
- `power_metrics`: metric_id (PK); facility_id (FK), timestamp, power_draw_kw, it_load_kw, cooling_power_kw, pue, cooling_cost. Natural grain: `(facility_id, timestamp)`.
- `network_metrics`: metric_id (PK); facility_id (FK), timestamp, bandwidth_utilization_pct, latency_ms, packet_loss_pct, throughput_mbps, network_availability_pct. Natural grain: `(facility_id, timestamp)`.
- `uptime_incidents`: incident_id (PK); facility_id (FK), server_id (FK), start_time, end_time, downtime_minutes, severity, root_cause, status.

All processed primary-key candidates are unique. Tested foreign keys have zero blank references and zero orphan values. Raw duplicate primary-key occurrences are 314 server metrics, 15 power metrics, and 13 network metrics.

## Raw-versus-processed evidence

Raw missing cells were measured as follows:

- Server metrics: CPU 342, memory 353, disk 358, network 320 (1,373 total).
- Power metrics: cooling power 22, PUE 32, cooling cost 18 (72 total).
- Network metrics: latency 36, packet loss 32, throughput 24 (92 total).

The processed equivalents contain no blank cells and no duplicate primary keys. The supplied issue register also declares controlled outliers and inconsistent status labels; their detailed independent validation belongs to Step 2, not Step 1.

## Metadata review

- `dataset_manifest.json`: authoritative package identity, seed, coverage, counts, and eight known evaluation events.
- `canonical_data_contract.json`: canonical modules and the rule that missing optional modules disable gracefully.
- `data_quality_issues.json`: declared injected raw issues and intended cleaning outcomes; it is a comparison baseline, not proof.
- `metric_definitions.yaml`: initial shared KPI definitions for SQL/AI and later Power BI validation.
- `business_glossary.yaml`: canonical terms, meanings, and synonyms.
- `default_aliases.json`: external-column synonym candidates.
- `schema_mapping_template.yaml`: explicit external-to-canonical mapping template.
- `ground_truth_anomalies.json`: evaluation answers only; never a production knowledge source.

## Folder purpose

- `raw`: immutable source evidence with deliberate quality defects; input to profiling and cleaning.
- `processed`: supplied trusted baseline used for comparison and, after independent validation, analytics consumers.
- `metadata`: contracts, definitions, manifest, and declared quality expectations.
- `adapters`: future external-schema mapping inputs.
- `evaluation`: test questions and expected outcomes kept outside production context.

## Architecture decision

The proposed architecture is sound for a portfolio-scale system. Keep Power BI and the AI assistant as separate consumers of the same canonical data and KPI definitions. Keep SQLite read-only to the AI path and keep generated SQL untrusted.

Two refinements are recommended before later coding:

1. Treat `data/raw` as immutable and generate cleaned output into a separate build location before comparing it with `data/processed`; never overwrite the supplied baseline.
2. Enforce evaluation isolation structurally: production loaders must allow-list `data/metadata`, `analytics`, and verified SQL examples rather than recursively scanning the repository.

No canonical schema change is needed at this stage.

## Finalized environment and stack

Use CPython 3.12 (64-bit). It is mature, supported by the selected libraries, and the inspected local runtime is Python 3.12.13. Avoid Python 3.14 for this project until all binary dependencies advertise stable support.

The finalized stack is Python 3.12, pandas, NumPy, PyYAML, SQLite from Python's standard library, Ollama's Python SDK, python-dotenv, scikit-learn TF-IDF/cosine retrieval initially, sqlglot, Streamlit, Plotly, pytest/pytest-cov, and Ruff. Power BI Desktop and DAX remain a separate consumer layer. LangChain, a vector database, cloud infrastructure, and the optional ML extension are intentionally deferred.

## Windows PowerShell setup

Run from the folder that should contain the project:

```powershell
cd "C:\Users\admin\Downloads\AI_Image_Classification_Final_Project_Import_Fixed"
py -3.12 -m venv "ai-data-center-intelligence\.venv"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "ai-data-center-intelligence\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
python -m pip install -r "ai-data-center-intelligence\requirements.txt"
```

If `py -3.12` reports that Python is unavailable, install 64-bit Python 3.12 from python.org, enable the Python launcher during setup, reopen PowerShell, and rerun the command.

The exact scaffold can be recreated with:

```powershell
$Project = "ai-data-center-intelligence"
$Folders = @(
  "app", "src", "scripts", "data\raw", "data\processed", "data\metadata",
  "database", "analytics", "adapters", "powerbi\documentation",
  "powerbi\screenshots", "powerbi\theme", "evaluation\private",
  "evaluation\results", "tests", "docs", "assets", "logs"
)
New-Item -ItemType Directory -Path $Project -Force
$Folders | ForEach-Object { New-Item -ItemType Directory -Path (Join-Path $Project $_) -Force }
```

## Verification commands and expected output

```powershell
cd "C:\Users\admin\Downloads\AI_Image_Classification_Final_Project_Import_Fixed\ai-data-center-intelligence"
python --version
python -m pip check
python -c "import pandas, numpy, yaml, ollama, dotenv, sklearn, sqlglot, streamlit, plotly, pytest; print('Environment OK')"
python scripts\inspect_dataset.py > step1_profile.json
```

Expected results: `Python 3.12.x`, `No broken requirements found.`, `Environment OK`, and a JSON profile showing processed row counts of 6, 430, 1,727,740, 24,108, 24,108, and 1,158.

## Dependency purpose

- pandas/NumPy: tabular cleaning, validation, and numerical work.
- PyYAML: shared metric, glossary, and mapping definitions.
- ollama/python-dotenv: local LLM access and configuration without an external API key.
- scikit-learn: lightweight retrieval baseline without a heavy framework.
- sqlglot: parse and validate generated SQLite SQL as an AST.
- Streamlit/Plotly: conversational UI and deterministic charts later.
- pytest/pytest-cov: automated verification and coverage.
- Ruff: fast linting and formatting checks.

## Never commit

Never commit `.env`, API keys, credentials, private keys, local virtual environments, logs containing questions/results, generated databases, evaluation results with sensitive prompts, or `evaluation/private`. The large CSVs are also ignored to avoid GitHub file-size problems; retain the original ZIP locally and document how authorized users obtain it.

## Step 1 verification checklist

- [x] Original ZIP inspected without regeneration.
- [x] All expected package folders and 21 files found.
- [x] All six raw and processed schemas inspected.
- [x] Counts, sizes, dates, candidate keys, missing cells, duplicates, and foreign-key coverage checked.
- [x] Actual counts match the manifest.
- [x] Metadata and adapter files reviewed.
- [x] Ground truth moved to an ignored, evaluation-only location.
- [x] Python 3.12 and the lightweight stack finalized.
- [x] Project scaffold, requirements, ignore rules, environment example, and repeatable inspector created.
- [ ] Fresh `.venv` created and dependencies installed (blocked locally because the Python launcher currently has no registered installation).
- [ ] Fresh-environment verification commands pass after Python 3.12 installation.

## Interview preparation

**Why separate raw and processed data?** Raw data preserves source evidence and makes cleaning reproducible; processed data provides a stable canonical input for consumers.

**Why validate processed data instead of trusting it?** A label such as “clean” is only a claim. Independent checks protect dashboards and AI answers from upstream mistakes.

**What is the grain?** The grain defines what one row represents. Examples are one facility, one server, one daily server measurement, or one incident.

**Why use candidate and natural keys as well as IDs?** IDs enforce identity, while natural composite keys such as facility plus date detect duplicate measurements at the business grain.

**Why SQLite first?** It is portable, reproducible, supports analytical SQL, and is adequate for a single-user portfolio demo. PostgreSQL would be preferable for concurrency, stronger access control, and production scale.

**Why Python 3.12?** It balances modern language support with broad compatibility across data, AI, and UI packages.

**Why not LangChain initially?** The required retrieval and prompting pipeline is small enough to implement transparently. Fewer abstractions make security, evaluation, and interview explanations clearer.

**How is evaluation leakage prevented?** The answer file lives in an ignored private directory, and later production retrieval must use explicit allow-lists rather than repository-wide discovery.
