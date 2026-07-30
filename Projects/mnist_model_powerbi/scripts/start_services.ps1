$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = $VenvPython

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment missing. Run INSTALL_PROJECT.ps1 first."
}

$VenvHealthy = $false
try {
    & $VenvPython --version *> $null
    $VenvHealthy = $LASTEXITCODE -eq 0
} catch {
    $VenvHealthy = $false
}

if (-not $VenvHealthy) {
    $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (-not (Test-Path $BundledPython)) {
        throw "The project virtual environment references a missing Python installation. Install Python 3.12 and run INSTALL_PROJECT.ps1 again."
    }

    # Reuse the existing Python 3.12 environment packages when the original
    # base interpreter was removed from this workstation.
    $Python = $BundledPython
    $VenvPackages = Join-Path $Root ".venv\Lib\site-packages"
    $env:PYTHONPATH = "$Root;$VenvPackages"
    $env:Path = "$(Join-Path $Root '.venv\Scripts');$env:Path"
}

Set-Location $Root

& (Join-Path $Root "scripts\stop_services.ps1")

& $Python -m scripts.verify_project
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$api = Start-Process $Python `
    -ArgumentList @("-m", "uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$LogDir\api.out.log" `
    -RedirectStandardError "$LogDir\api.err.log" `
    -PassThru

$watcher = Start-Process $Python `
    -ArgumentList @("-u", "-m", "app.main") `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$LogDir\watcher.out.log" `
    -RedirectStandardError "$LogDir\watcher.err.log" `
    -PassThru

@{ api = $api.Id; watcher = $watcher.Id } |
    ConvertTo-Json |
    Set-Content (Join-Path $Root ".service_pids.json")

Write-Host "API: http://127.0.0.1:8000/health"
Write-Host "Drop images into: $Root\data\incoming"
