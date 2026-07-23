$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "Inventory_Control_Tower.pbip"
if (-not (Test-Path $project)) { throw "PBIP file not found: $project" }
Start-Process $project
