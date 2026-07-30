$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Edit its passwords and API key before production use."
}

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-bridge.txt
Write-Host "Excel bridge Python: $ProjectRoot\.venv\Scripts\python.exe"
Write-Host "Next: docker compose up --build -d"
