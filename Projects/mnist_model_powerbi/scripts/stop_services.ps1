$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PidFile = Join-Path $Root ".service_pids.json"
if (Test-Path $PidFile) {
  $pids = Get-Content $PidFile | ConvertFrom-Json
  foreach ($id in @($pids.api,$pids.watcher)) {
    if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) {
      & taskkill.exe /PID ([string]$id) /T /F *> $null
    }
  }
  Remove-Item $PidFile -Force
}
Write-Host "Services stopped."
