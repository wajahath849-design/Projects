# Installation and execution guide

## Primary Windows workflow

Install 64-bit Python 3.12, SQL Server Express, and Microsoft ODBC Driver 18. Enable the
`SQLEXPRESS` instance and use Windows authentication.

```powershell
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\initialize_database.py
.\.venv\Scripts\python.exe scripts\generate_m5_sample.py
.\.venv\Scripts\python.exe scripts\load_m5_data.py --sample
.\.venv\Scripts\python.exe scripts\generate_enterprise_data.py --sample
.\.venv\Scripts\python.exe scripts\verify_project.py
```

Calling the environment Python directly avoids PowerShell activation-policy problems.

## Full M5 mode

Place the three original M5 files in `data/raw/m5`, then use `load_m5_data.py` without
`--sample` and `build_features.py --full`. Chunk size, paths, and timeouts are configurable.
The full workflow uses chunked ingestion, Parquet intermediates, SQL bulk operations, and
reusable model artifacts; memory and execution time depend on the selected subset.

## Docker

Windows-authenticated SQL Server Express remains the primary workflow. A Linux API container
cannot automatically reuse the host Windows token, so create a least-privilege SQL login,
copy `.env.docker.example` to `.env.docker`, and set secrets locally:

```powershell
docker compose --env-file .env.docker up --build api
```

For the optional SQL Server Developer container:

```powershell
docker compose --env-file .env.docker --profile container-sql up --build
```

Never commit `.env`, `.env.docker`, SQL passwords, tokens, or connection secrets.
