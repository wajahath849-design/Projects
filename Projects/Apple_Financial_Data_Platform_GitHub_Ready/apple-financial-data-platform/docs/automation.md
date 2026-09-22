# Automated Refresh

## Windows Task Scheduler

The repository includes a scheduled-refresh script and an optional task-registration script.

### Run the refresh manually

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\scheduled_refresh.ps1
```

The script activates the virtual environment, runs the ETL and writes a dated log under `logs/`.

### Register a daily task

Open PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_scheduled_task.ps1 -DailyTime "07:00"
```

The task is registered as `Apple Financial ETL Refresh`.

### Remove the task

```powershell
Unregister-ScheduledTask -TaskName "Apple Financial ETL Refresh" -Confirm:$false
```

## Power BI refresh

For Power BI Desktop, refresh after the SQL ETL completes. For Power BI Service with an on-premises SQL Server, configure an on-premises data gateway and schedule the semantic-model refresh after the ETL task.

## Operational checks

Use `reporting.vw_ETLRunHistory` and `reporting.vw_DataQualityIssues` to confirm that the latest run succeeded before publishing updated reports.
