$ErrorActionPreference = "Stop"

& .\.venv\Scripts\Activate.ps1
docker compose up -d
apple-finance-etl init-db
apple-finance-etl run --years 10
pytest

Write-Host "Pipeline and tests completed." -ForegroundColor Green
