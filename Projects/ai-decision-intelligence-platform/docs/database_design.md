# Database design

## Purpose

`AIDecisionIntelligence` is a star-schema-compatible SQL Server analytical
database for forecast, inventory, optimization, scenario, and quality reporting.
It uses surrogate integer dimension keys and bigint identity fact keys. Business
identifiers remain unique for traceability to M5 or synthetic enterprise data.

## Object inventory

- 9 dimensions: date, product, category, store, state, warehouse, supplier,
  scenario, and model.
- 16 facts: sales, price, inventory, purchase orders and lines, supplier
  performance, transportation, forecasts and metrics, model runs and
  explanations, stockout risk, recommendations and allocations, scenario
  results, and data quality.
- 8 reporting views corresponding to the required Power BI subject areas.

## Integrity and audit design

Facts use foreign keys to enforce valid analytical relationships. Check
constraints reject invalid quantities, probabilities, statuses, inventory
reconciliation, and solver states. Facts include `CreatedAt`, `UpdatedAt`,
`PipelineRunID`, `SourceSystem`, and `DataVersion`. Synthetic seed rows are
identified as `PHASE1_SEED` and are not represented as real Walmart operations.

## Deployment

The ordered scripts in `database/schema` are idempotent. The initializer creates
the database from `master`, applies schema scripts transactionally within the
target database, applies minimal seeds, and then verifies metadata and behavior.
It never drops an existing database or table.

The verification performs a transactional test insert and rolls it back, so no
test category remains after completion.
