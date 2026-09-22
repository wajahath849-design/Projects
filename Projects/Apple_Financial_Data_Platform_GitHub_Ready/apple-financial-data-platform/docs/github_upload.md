# Upload to GitHub

```powershell
git init
git add .
git commit -m "Build Apple financial data migration and SQL reporting platform"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/apple-financial-data-platform.git
git push -u origin main
```

Before pushing:

- Do not commit `.env`.
- Do not commit passwords, database backups or generated raw SEC JSON.
- Run `pytest` and `ruff check src tests`.
- Add dashboard screenshots under `docs/screenshots/` after building the Power BI report.
- Add the repository topics: `python`, `sql-server`, `power-bi`, `etl`, `sec-edgar`, `xbrl`, `data-engineering`, `financial-analysis`.

Suggested GitHub description:

> End-to-end Python ETL, SQL Server and Power BI platform for migrating, validating and reporting Apple SEC EDGAR/XBRL financial data.
