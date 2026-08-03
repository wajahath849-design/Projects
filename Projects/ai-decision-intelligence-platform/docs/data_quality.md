# Data-quality framework

## Gate behavior

The quality runner evaluates every configured rule, stores all outcomes under one
`PipelineRunID`, and writes JSON, CSV, and HTML reports. A critical failed check
closes the gate and the command exits nonzero. Downstream pipelines can call
`assert_latest_quality_gate` before processing.

An execution error rolls back the entire quality run, preventing partial results
from appearing as a valid gate decision.

## Checks

- Missing required sales and inventory fields
- Duplicate sales and inventory business grains
- Invalid or orphaned fact keys
- Invalid calendar attributes and sales date ranges
- Negative demand, prices, forecasts, or forecast lower bounds
- Daily inventory reconciliation and nonnegative closing stock
- Supplier capacity below minimum-order quantities
- Warehouse capacity overruns
- Purchase-order lifecycle inconsistencies

SQL constraints already prevent many invalid writes. The quality framework is an
independent analytical safeguard that detects legacy, bulk-loaded, disabled-
constraint, or cross-table inconsistencies.

## Reports and persistence

Reports are written to `reports/data_quality` using the quality run UUID. Stored
results include records checked, failed records, failure percentage, severity,
status, audit fields, and a JSON description. The quality run's actual UTC date
is added to `DimDate` when necessary and used by `FactDataQuality`.
