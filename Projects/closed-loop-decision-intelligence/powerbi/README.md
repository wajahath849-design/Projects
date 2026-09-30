# Power BI implementation package

This is an implementation specification and connection package, **not a fabricated
PBIX**. Power BI Desktop on Windows is required to create the report manually.
The report has not been opened or visually verified in Power BI during this build.

1. Complete PostgreSQL ingestion and `python -m src.cli transform` (runs dbt build).
2. In Desktop, Get Data → PostgreSQL database; server `localhost:5432`, database
   `decision_intelligence`, Import mode. Enter credentials through the connector,
   never in M source. Container-to-container names do not work from Desktop.
3. Load the models listed in `model_design.md`. Add Date columns from timestamps.
4. Configure one-to-many, single-direction relationships; disable automatic date/time.
5. Paste the DAX measures from `measures.md` and assemble `dashboard_spec.md`.
6. Refresh after pipeline completion and after impact verification. Validate total
   paid revenue against SQL, then validate one complete Decision Ledger row.

The warehouse has no paid-cloud dependency. Desktop refresh is local; scheduled
Power BI Service publishing/gateways are deliberately outside this project.
