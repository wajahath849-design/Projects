[CmdletBinding()]
param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectRoot

try {
    $Python = Get-Command py -ErrorAction Stop
    & $Python.Source -3.12 --version
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 is not registered with the Python launcher. Install 64-bit Python 3.12, then retry."
    }
    & $Python.Source -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.12 could not create the .venv environment."
    }
    & .\.venv\Scripts\python.exe --version
    if ($LASTEXITCODE -ne 0) {
        throw "The .venv environment is not usable. Remove only the .venv folder and rerun setup."
    }
    if (-not $SkipInstall) {
        & .\.venv\Scripts\python.exe -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            throw "pip upgrade failed."
        }
        & .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) {
            throw "Dependency installation failed."
        }
    }
    if (-not (Test-Path -LiteralPath .env)) {
        Copy-Item -LiteralPath .env.example -Destination .env
    }
    & .\.venv\Scripts\python.exe scripts\verify_environment.py
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    & .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest-tmp
    exit $LASTEXITCODE
}
catch {
    Write-Error "Environment setup failed: $($_.Exception.Message)"
    exit 1
}
