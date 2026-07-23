# Validation Report

Validation date: 2026-07-23

## Passed in this environment

- Python source compilation: `python -m compileall -q app scripts`
- Automated test suite: **15 passed**
- Docker Compose YAML parsing
- Required project-file presence check
- PostgreSQL 18 container volume target check: `/var/lib/postgresql`
- Excel workbook structural inspection
- Excel formula-error scan: no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, or `#N/A` matches in the validated workbook
- Excel visual render inspection of the operational override form
- Reproducible sample CSV generation

## Covered by automated tests

- Variable-demand/variable-lead-time safety stock
- Service-level validation
- MOQ and order-multiple rounding
- Expected stockout-date calculation
- LightGBM and seasonal-naive forecast behavior
- Override request validation
- Cross-warehouse transfer allocation
- External-signal and manual-override combination
- SQL asset checks for current-run views, multi-line PO lead-time keys, audit fields, and job recovery fields
- Supplier-document parsing helpers

## Not executable in this environment

Docker Engine and a PostgreSQL server are not installed in the execution environment used to build this package. Therefore, the following must be run on the deployment workstation before production acceptance:

1. `docker compose up --build -d`
2. `docker compose exec api python scripts/load_demo.py`
3. `python scripts/smoke_test.py`
4. Power BI refresh against the running PostgreSQL database
5. Excel `.xlsm` macro execution on Windows with Excel Desktop
6. Classic Outlook draft generation, or replacement with Microsoft Graph/Power Automate

## Production acceptance gates

- Reconcile source WMS totals against the database.
- Backtest by SKU velocity/category and review WAPE and bias.
- Load-test operational Power BI pages.
- Validate worker restart, duplicate file, retry, and failover behavior.
- Keep PO auto-send disabled until routing and approval controls are signed off.
- Replace the shared API key with enterprise identity before broad deployment.
