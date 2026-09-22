$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Update SEC_USER_AGENT and database credentials before running ETL." -ForegroundColor Yellow
}

python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

Write-Host "Environment ready." -ForegroundColor Green
Write-Host "Next: docker compose up -d; apple-finance-etl init-db; apple-finance-etl run"
