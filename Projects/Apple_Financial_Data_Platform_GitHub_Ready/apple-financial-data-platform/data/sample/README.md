# Offline Sample Data

These files are generated from the small SEC-shaped fixture in `tests/fixtures/companyfacts_minimal.json`. They exist only to demonstrate the transformed schema without an internet or database connection.

They are not presented as a complete or current Apple financial dataset. Run the live pipeline to obtain current SEC EDGAR filing data:

```powershell
apple-finance-etl run --years 10 --force-refresh
```
