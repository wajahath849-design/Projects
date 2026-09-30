param([switch]$Offline)
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if ($Offline) {
    & .\.venv\Scripts\python.exe -m src.cli --offline demo
} else {
    docker compose exec api python -m src.cli demo
}
exit $LASTEXITCODE
