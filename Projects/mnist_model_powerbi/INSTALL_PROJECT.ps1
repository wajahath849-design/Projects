$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

py -3.12 -m venv .venv
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $Python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m scripts.bootstrap_database
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m scripts.verify_project --allow-missing-models
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Base installation complete. Add trained model files and metadata, then run REGISTER_MODELS.bat."
