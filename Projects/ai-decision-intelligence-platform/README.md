# AI Decision Intelligence Platform

A production-style portfolio project that turns retail demand forecasts into
explainable inventory and replenishment decisions. Development is deliberately
phased; the repository currently contains the environment and SQL Server
database, forecasting, explainability, inventory, optimization, scenario, API,
reporting, deployment, and verification layers through Phase 17.

## Business problem

The completed platform will answer what demand is expected, which inventory is
at risk, what should be purchased and allocated, and why each forecast and
recommendation was produced.

## Planned architecture

M5 retail history flows through validated ingestion, leakage-safe forecasting,
inventory-risk analysis, OR-Tools optimization, SQL Server, FastAPI, and Power
BI. Seasonal Naive, XGBoost, and LightGBM will be compared using time-based
validation; no model is predetermined to win.

## Phase 0 quick start (Windows PowerShell)

Prerequisites: 64-bit Python 3.12, PowerShell, and Git. SQL Server Express and
Microsoft ODBC Driver 18 are checked now but become required in Phase 1.

```powershell
cd ai-decision-intelligence-platform
py -3.12 --version
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\verify_environment.py
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest-tmp
```

Virtual-environment activation is optional. Calling its Python executable
directly avoids conflicts with another installed Python version and works when
PowerShell script execution is restricted. For one-command setup, run
`scripts\setup_environment.cmd`; its execution-policy override applies only to
that child PowerShell process and does not alter the system policy.

If `.venv` reports that its Python executable cannot be found, it was created
from a Python installation that has since moved or been removed. After Python
3.12 is installed and `py -3.12 --version` succeeds, delete only `.venv` and
recreate it with the commands above.

The verifier exits with code `0` when all Phase 0 requirements pass. Add
`--strict-future-stack` to make SQL Server ODBC and future ML imports mandatory.

## Dataset

The M5 dataset is not redistributed. In Phase 2, users will manually place
`calendar.csv`, `sales_train_validation.csv`, and `sell_prices.csv` in
`data/raw/m5/`. Synthetic enterprise operations created later will be clearly
identified and will not represent actual Walmart operations.

## SQL Server foundation

Phase 1 targets `localhost\SQLEXPRESS` with Windows Authentication and ODBC
Driver 18. It creates `AIDecisionIntelligence`, 9 dimensions, 16 facts, 8 Power
BI views, foreign keys, validation constraints, and analytical indexes. Schema
and seed scripts are idempotent and can be rerun safely.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\initialize_database.py
.\.venv\Scripts\python.exe scripts\initialize_database.py --verify-only
.\.venv\Scripts\python.exe -m decision_intelligence.cli initialize-database --verify-only
```

The initializer inserts only minimal Phase 1 records. Full M5 ingestion remains
deferred to Phase 2.

## M5 ingestion

Phase 2 validates and incrementally loads `calendar.csv`,
`sales_train_validation.csv`, and `sell_prices.csv`. Original M5 files are
manually supplied under `data/raw/m5` and are excluded from Git. Wide sales data
is melted in bounded day blocks, while weekly prices are expanded to the daily
analytical grain used by SQL Server.

To test without downloading M5, generate and load the clearly labeled synthetic
sample:

```powershell
.\.venv\Scripts\python.exe scripts\generate_m5_sample.py
.\.venv\Scripts\python.exe scripts\load_m5_data.py --sample --chunk-size 3
.\.venv\Scripts\python.exe -m decision_intelligence.cli load-data --sample
```

Expected sample counts are 28 calendar rows, 8 product-store sales series, 224
daily sales facts, 40 weekly price inputs, and 224 daily price facts.

## Synthetic enterprise operations

Phase 3 converts loaded demand into reproducible operational test data. The
generated supplier, warehouse, lane, purchase-order, inventory, and constraint
records are synthetic and do not describe Walmart operations.

```powershell
.\.venv\Scripts\python.exe scripts\generate_enterprise_data.py --sample
.\.venv\Scripts\python.exe -m decision_intelligence.cli generate-data --sample
```

Generated CSVs are written to `data/processed/enterprise`. SQL rows use
`SourceSystem = SYNTHETIC_ENTERPRISE`. Migration `008` adds the documented
`BridgeSupplierProduct` and `BusinessConstraint` support tables without changing
or removing Phase 1 objects.

## Data-quality gate

Phase 4 runs 13 SQL-backed checks across completeness, uniqueness, validity,
referential integrity, reconciliation, capacity, and purchase-order lifecycle.
Every result is stored in `FactDataQuality` and exported as JSON, CSV, and HTML.
Any critical failure returns a nonzero exit code and blocks downstream processing.

```powershell
.\.venv\Scripts\python.exe scripts\run_data_quality.py
.\.venv\Scripts\python.exe -m decision_intelligence.cli run-quality
```

## Forecasting and explainability (Phases 5-10)

The sample workflow builds strictly shifted date, demand, price, and inventory
features; evaluates Seasonal Naive, XGBoost, and LightGBM on the same chronological
holdout; and selects the production model from measured WAPE, bias, runtime, and
residual variability. It then produces daily 7/30/90-day forecasts, prediction
intervals, confidence scores, aggregate exports, and ranked local SHAP explanations.

```powershell
.\.venv\Scripts\python.exe -m decision_intelligence.cli build-features
.\.venv\Scripts\python.exe -m decision_intelligence.cli train-models
.\.venv\Scripts\python.exe -m decision_intelligence.cli evaluate-models
.\.venv\Scripts\python.exe -m decision_intelligence.cli generate-forecasts
.\.venv\Scripts\python.exe -m decision_intelligence.cli generate-explanations
```

Details, null handling, artifacts, metric definitions, and manual SQL checks are in
[`docs/forecasting.md`](docs/forecasting.md).

## Inventory, optimization, and scenarios (Phases 11-13)

Inventory intelligence calculates service-level safety stock, reorder points, safe days
of supply, projected inventory, uncertainty-aware stockout probabilities, and five status
classes. OR-Tools then minimizes purchase, transport, holding, stockout, late-risk, and
excess costs subject to coverage, capacity, budget, MOQ/maximum, eligibility, lead-time,
nonnegativity, and integer constraints. Every result is independently validated.

```powershell
.\.venv\Scripts\python.exe -m decision_intelligence.cli inventory
.\.venv\Scripts\python.exe -m decision_intelligence.cli optimize
.\.venv\Scripts\python.exe -m decision_intelligence.cli run-scenarios
```

Ten deterministic scenario types preserve baseline results and report demand, revenue,
inventory, stockout, order, component-cost, total-cost, profit, and protected-revenue impact.

## API and reporting (Phases 14-15)

```powershell
.\.venv\Scripts\python.exe -m uvicorn decision_intelligence.api.main:app --reload
.\.venv\Scripts\python.exe -m decision_intelligence.cli export-powerbi
```

Swagger UI is available at `http://127.0.0.1:8000/docs`. The Power BI folder contains real
SQL views, 37 DAX measures, a theme, model and Power Query instructions, seven page layouts,
visual mappings, formatting, tooltips, drill-through guidance, and checks. It does not claim
to contain a generated PBIX file.

## Verification and automation (Phases 16-17)

```powershell
.\.venv\Scripts\python.exe scripts\verify_project.py
docker compose --env-file .env.docker up --build api
```

The repository includes a non-root API image, optional SQL Server container profile, health
checks, local Make targets, and GitHub Actions. SQL Server Express with Windows authentication
remains the primary local workflow. `PROJECT VERIFICATION PASSED` is printed only after all
critical database, model, optimization, scenario, API, Power BI, documentation, lint, type,
unit, and integration checks pass.

## Documentation

- [Architecture](docs/architecture.md)
- [Installation](docs/installation.md)
- [Forecasting details](docs/forecasting.md) and [model card](docs/model_card.md)
- [Data dictionary](docs/data_dictionary.md)
- [API guide](docs/api.md)
- [Power BI guide](docs/power_bi_guide.md)
- [Interview guide](docs/interview_guide.md) and [CV description](docs/cv_description.md)
- [Release checklist](docs/release_checklist.md)

## Ethics and limitations

The supplied enterprise operations are reproducible synthetic data and are never represented
as real Walmart or supplier operations. The short sample is unsuitable for business claims.
The API has no production authentication, uncertainty is not formally calibrated, and all
purchasing recommendations require human review. This project is portfolio-grade and
production-style; it is not represented as production-ready.
