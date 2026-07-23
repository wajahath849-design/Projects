# Automated Intelligent Inventory Replenishment & Supply Chain Analytics System

A runnable reference implementation of a four-tier supply-chain stack:

1. **Excel + VBA** for validated operational overrides and approved purchase-order output.
2. **Python** for ingestion, forecasting, safety-stock calculation, network rebalancing, and job processing.
3. **PostgreSQL** as the governed source of truth and audit layer.
4. **Power BI** as the executive and operational control tower.

## What is implemented

- Dockerized PostgreSQL, FastAPI service, and asynchronous worker.
- Normalized dimensions and facts for SKUs, warehouses, suppliers, transactions, snapshots, lead times, overrides, forecasts, recommendations, transfers, purchase orders, and model runs.
- Idempotent CSV ingestion using business keys and PostgreSQL `ON CONFLICT` upserts.
- PDF text extraction with optional OCR fallback and duplicate detection by SHA-256 hash.
- Allow-listed HTTPS adapter for weather, freight-delay, or other external JSON signals, with scale/offset/clamp normalization.
- SKU/warehouse demand forecasts using LightGBM lag/rolling features.
- Seasonal-naive fallback for sparse or short histories.
- Holdout metrics: MAE, RMSE, WAPE, and forecast bias.
- Safety stock for variable demand and variable lead time.
- Reorder points, target stock, expected stockout dates, risk bands, MOQ, and order-multiple rounding.
- Regional external demand/lead-time modifiers and cross-warehouse surplus transfer recommendations before external purchase quantities are finalized.
- Approval-controlled operational overrides with complete submitter/approver audit history.
- Excel-to-Python background submission through a small bridge process.
- Purchase-order PDF generation and classic Outlook email automation.
- Power BI star-schema instructions, control-tower page design, and ready-to-paste DAX measures.
- Worker heartbeats, stale-job recovery with capped attempts, demo data generation, and automated tests.

## Important architecture decisions

### Excel submits work; it does not train models

The workbook writes a small JSON request and starts the Python bridge in the background. The API records the override, and the worker processes approved changes. This prevents frozen workbooks, concurrent model runs, duplicate writes, and unsafe command-line parameter injection.

### Safety-stock formula

The node-level baseline is:

`SS = Z × sqrt(L̄ × σD² + D̄² × σL²)`

Where:

- `Z` is the service-level normal quantile.
- `D̄` is average daily demand.
- `σD` is daily demand standard deviation.
- `L̄` is average lead time in days.
- `σL` is lead-time standard deviation in days.

Then:

- `Reorder Point = D̄ × L̄ + SS`
- `Target Stock = D̄ × (L̄ + Review Period) + SS`

This formula alone is **single-echelon**. The package adds a practical multi-location stage that reallocates safe surplus between warehouses and reduces the remaining external purchase quantity. A fully stochastic multi-echelon inventory optimization model would additionally require network service-level constraints, transfer costs, capacities, and optimization across the complete distribution graph.

### Forecast model policy

LightGBM was selected as the production reference model because this implementation uses SKU/location lag features, calendar features, and rolling statistics in one pipeline. Prophet is not required by the runnable package.

- LightGBM is used when enough dense history exists.
- Seasonal-naive forecasting is used when history is sparse or shorter than the configured threshold.
- Forecasts are never allowed below zero.
- Operational overrides adjust replenishment calculations without rewriting the underlying base forecast.
- A model run, model name, version, parameters, dates, warnings, and accuracy metrics are stored for traceability.

## Project structure

```text
app/
  api.py                    FastAPI bridge and approval endpoints
  worker.py                 Background queue worker
  jobs.py                   Safe PostgreSQL job claiming with SKIP LOCKED
  ingestion.py              CSV ingestion and validation
  document_ingestion.py     PDF/OCR extraction and parsing
  external_signals.py       Allow-listed REST signal ingestion
  forecasting.py            LightGBM and fallback forecasting
  safety_stock.py           Replenishment calculations
  network_rebalancing.py    Cross-warehouse stock transfer netting
  pipeline.py               End-to-end orchestration
  adjustments.py            External-signal and approved-override combination
  excel_bridge.py           Background process started by VBA
sql/
  00_schema.sql             Tables, constraints, date dimension, indexes
  01_views.sql              Power BI-ready views
  02_seed_demo.sql          Demo dimensions
vba/
  *.bas                     Importable Excel VBA modules
  WORKBOOK_SETUP.md         Named ranges and workbook setup
powerbi/
  Measures.dax              Ready-to-paste measures
  POWER_BI_BUILD.md         Model, relationships, and page layout
scripts/
  generate_sample_data.py   Reproducible demo generator
  load_demo.py              Ingest demo and run the pipeline
  setup_windows.ps1         Host-side Excel bridge setup
  smoke_test.py             API and queue smoke test
tests/                     Automated unit and asset checks
Inventory_Operations_Template.xlsx  Excel field-operations workbook
requirements-dev.txt       Development/test dependencies
VALIDATION_REPORT.md        Executed checks and remaining acceptance gates
```

## Prerequisites

- Docker Desktop with Docker Compose.
- Python 3.12 on the Windows Excel workstation.
- Excel Desktop with macros enabled for the trusted workbook.
- Power BI Desktop.
- Classic Outlook only for the included COM/VBA email module. For new Outlook or unattended enterprise sending, replace that module with Microsoft Graph or Power Automate.

## 1. Configure environment

From PowerShell in the project root:

```powershell
Copy-Item .env.example .env
notepad .env
```

Change at least:

- `POSTGRES_PASSWORD`
- `DATABASE_URL` password
- `API_KEY`
- `EXTERNAL_API_ALLOWED_HOSTS`
- `ALLOWED_INGESTION_ROOTS`

Do not commit `.env`.

## 2. Start PostgreSQL, API, and worker

```powershell
docker compose up --build -d
```

Check containers:

```powershell
docker compose ps
```

Check the API:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 3. Generate and load demo data

During early development, SQL init scripts run only when PostgreSQL creates a new empty volume. To rebuild the demo database after changing schema files:

```powershell
docker compose down -v
docker compose up --build -d
```

`down -v` deletes the local database volume, so never use it against a production database.


The repository already includes generated demo CSVs. Regenerate them inside the API container when needed:

```powershell
docker compose exec api python scripts/generate_sample_data.py
```

Load the demo through the API container and execute the complete pipeline:

```powershell
docker compose exec api python scripts/load_demo.py
```

Inspect results in PostgreSQL:

```sql
SELECT * FROM inventory.vw_inventory_control_tower;
SELECT * FROM inventory.vw_transfer_recommendations;
SELECT * FROM inventory.vw_supplier_performance;
SELECT * FROM inventory.vw_forecast_accuracy;
```

## 4. Configure the Excel bridge

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

Create the Windows user environment variable used by the bridge:

```powershell
[Environment]::SetEnvironmentVariable("INVENTORY_API_KEY", "the-same-key-as-.env", "User")
```

Restart Excel after setting the variable.

Follow `vba/WORKBOOK_SETUP.md`, import the `.bas` modules, and configure:

- `cfgPythonExe` = `<project>\.venv\Scripts\python.exe`
- `cfgProjectRoot` = project folder
- `cfgApiUrl` = `http://localhost:8000`

The override is recorded as `PENDING`. A separate approver must approve it before it changes replenishment calculations.

## 5. Approve an override

Example API decision:

```powershell
$headers = @{ "X-API-Key" = $env:INVENTORY_API_KEY }
$body = @{ approved_by = "manager@example.com"; approve = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/overrides/1/decision" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Approval queues an `OVERRIDE_RECALC` job automatically. It reuses the latest successful base forecast and recalculates replenishment/transfer recommendations without retraining every SKU model.

## 6. Queue a full pipeline run

```powershell
$headers = @{ "X-API-Key" = $env:INVENTORY_API_KEY }
$body = @{
  job_type = "FULL_PIPELINE"
  payload = @{ horizon_days = 90 }
  requested_by = "planner@example.com"
  priority = 100
} | ConvertTo-Json -Depth 4

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/jobs" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

Use the returned job ID:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/jobs/<job-id>" `
  -Headers $headers
```

## 7. Ingest a normalized external signal

External inputs are converted into one of two operational modifiers before replenishment calculation:

- `DEMAND_MULTIPLIER` — multiplies historical demand statistics and the current base forecast.
- `LEAD_TIME_PENALTY_DAYS` — adds days to the selected historical or contractual lead time.

Example job request for a weather anomaly that is converted to a bounded demand multiplier:

```powershell
$headers = @{ "X-API-Key" = $env:INVENTORY_API_KEY }
$body = @{
  job_type = "INGEST_EXTERNAL_SIGNAL"
  requested_by = "planner@example.com"
  priority = 80
  payload = @{
    url = "https://api.example.com/weather/anomaly"
    region = "North"
    signal_type = "DEMAND_MULTIPLIER"
    value_path = "data.anomaly_index"
    source_name = "Weather Provider"
    scale = 0.05
    offset = 1.0
    min_value = 0.8
    max_value = 1.5
    signal_date = "2026-07-23"
  }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/jobs" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

The hostname must be present in `EXTERNAL_API_ALLOWED_HOSTS`. Normalize provider-specific values deliberately; do not feed raw temperature, rainfall, or delay indices directly into reorder quantities without an approved business mapping.

## 8. Connect Power BI

In Power BI Desktop:

1. Get Data -> PostgreSQL database.
2. Server: `localhost:5432`.
3. Database: `inventory`.
4. Enter the PostgreSQL username and password from `.env`.
5. Follow `powerbi/POWER_BI_BUILD.md`.
6. Paste measures from `powerbi/Measures.dax`.

Recommended model:

- Import dimensions, historical demand, current/historical forecasts, current/historical replenishment, accuracy, and supplier facts.
- DirectQuery only the current inventory/alert view when near-real-time display is genuinely required.
- Use incremental refresh on large dated fact tables.

## Operational scheduling

A typical production cadence is:

- Inventory snapshots: every 15–60 minutes.
- Transactions: incremental every 5–15 minutes or event-driven.
- External signals: hourly or daily, depending on the source.
- Replenishment recalculation: after approved overrides and at least daily.
- Full model retraining: nightly or weekly, depending on demand volatility.
- Power BI import refresh: after the pipeline completes.

Do not retrain every model for every Excel edit. A targeted recalculation or queued batch is safer and cheaper.

## Performance design

- Composite indexes cover SKU/warehouse/date access patterns.
- Dimensions use stable surrogate keys and unique business codes.
- Ingestion is idempotent.
- SQLAlchemy sends batched parameter sets instead of row-by-row commits.
- The worker claims jobs with `FOR UPDATE SKIP LOCKED`, maintains heartbeats, and recovers abandoned jobs up to a capped attempt count.
- Forecast facts and large demand facts are suitable for Power BI incremental refresh.
- The current reference worker is single-process. For tens of thousands of independent SKU/location models, shard jobs by region/category or run multiple workers with controlled database connection pools.

## Security and governance

Before production deployment:

- Put the API behind HTTPS and an authenticated reverse proxy.
- Replace the shared API key with corporate identity/OAuth where possible.
- Create separate PostgreSQL roles for ingestion, API writes, worker writes, and Power BI read-only access.
- Use Alembic, Flyway, or an equivalent migration process after the initial deployment; Docker initialization scripts only build a fresh database.
- Restrict external API hosts and never accept arbitrary URLs from Excel users.
- Store secrets in a secret manager, not workbooks, source code, or command-line arguments.
- Digitally sign the VBA project and use a trusted workbook location.
- Keep purchase-order automatic sending disabled until approval, audit, and supplier routing have been tested.
- Add data-retention rules for extracted PDF text because invoices can contain sensitive commercial data.

## Testing

Install development dependencies and run unit tests:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Run the API smoke test:

```powershell
$env:INVENTORY_API_KEY = "the-same-key-as-.env"
python scripts/smoke_test.py
```

The included test suite currently contains 15 checks covering:

- Safety-stock mathematics.
- MOQ/order-multiple rounding.
- Expected stockout date.
- LightGBM/fallback forecast behavior.
- Override validation.
- Cross-warehouse transfer allocation.

## Production acceptance checklist

- Reconcile at least 30 days of WMS transactions and snapshots against source totals.
- Validate timezone treatment and warehouse-local cut-off times.
- Backtest by SKU velocity class and report WAPE/bias, not only a global average.
- Approve service levels by category rather than using one global default forever.
- Verify lead-time outliers, partial receipts, cancellations, and supplier substitutions.
- Test duplicate files, duplicate transactions, API retries, worker restarts, and database failover.
- Confirm that internal transfer recommendations do not violate capacity, shelf life, hazardous-material, or regional restrictions.
- Run PO generation in display-only mode before allowing automatic sending.
- Load-test DirectQuery pages and move slow calculations into SQL/materialized views when necessary.
