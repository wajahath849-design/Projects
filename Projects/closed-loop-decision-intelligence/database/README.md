# Warehouse initialization

`init/001_warehouse.sql` is generated from the SQLAlchemy relational contracts.
`init/002_ledger.sql` installs the ledger view. PostgreSQL's container executes them
only when initializing an empty warehouse volume. API startup also applies idempotent
table creation and the ledger view definition. Neither path removes existing data.

Regenerate reviewed DDL with `python -m scripts.build_contracts`. New installations
receive the regenerated schema. Existing schema changes require an explicit reviewed
migration: SQLAlchemy `create_all` does not migrate columns in existing tables.
`migrations/002_ledger.sql` is the versioned view definition; this project does not
pretend to include a full migration runner or an upgrade history for future changes.

Production databases need separate roles for ingestion, transformation, analytics,
BI and evaluation. The local owner account is suitable only for this isolated demo.
The hidden-label schema is never used by detector/investigator code; production
permissions should enforce that boundary as well as the tested code boundary.
