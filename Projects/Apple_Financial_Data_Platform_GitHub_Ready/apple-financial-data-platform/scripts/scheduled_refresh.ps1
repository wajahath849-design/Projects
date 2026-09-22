$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$LogDirectory = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDirectory "etl_$Timestamp.log"

try {
    & "$ProjectRoot\.venv\Scripts\Activate.ps1"
    apple-finance-etl run --years 10 *>&1 | Tee-Object -FilePath $LogFile
    exit 0
}
catch {
    $_ | Out-File -FilePath $LogFile -Append
    exit 1
}
