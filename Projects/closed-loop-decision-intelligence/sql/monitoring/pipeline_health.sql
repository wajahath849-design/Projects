SELECT workflow_name, status, COUNT(*) AS executions,
       AVG(EXTRACT(EPOCH FROM (end_time - start_time))) AS mean_duration_seconds,
       SUM(rows_processed) AS rows_processed
FROM monitoring.pipeline_runs
WHERE start_time >= :since
GROUP BY workflow_name, status
ORDER BY workflow_name, status;
