$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12+ is required' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe scripts/configure.py
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker startup failed; check that Docker Desktop is running Linux containers' }
