param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')]
    [string]$DailyTime = "07:00"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RefreshScript = Join-Path $ProjectRoot "scripts\scheduled_refresh.ps1"

$Action = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RefreshScript`""

$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask `
    -TaskName "Apple Financial ETL Refresh" `
    -Description "Refresh Apple SEC EDGAR financial data in SQL Server." `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Force

Write-Host "Scheduled task registered for $DailyTime daily." -ForegroundColor Green
