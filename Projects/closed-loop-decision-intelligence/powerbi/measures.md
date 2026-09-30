# DAX measures

Table names below assume Navigator names are shortened to their unqualified names.
Measures over `cohort_mart` should use dimensions related to that table. For the
transaction star, use the separate order measures. Never add both representations.

```dax
Revenue = SUM(cohort_mart[revenue])
Orders = SUM(cohort_mart[orders])
Sessions = SUM(cohort_mart[sessions])
Conversion = DIVIDE([Orders], [Sessions])
Tracking Coverage = DIVIDE(SUM(cohort_mart[sessions]), SUM(cohort_mart[server_sessions]))
Conversion Trusted = IF([Tracking Coverage] >= 0.95, [Conversion])
AOV = DIVIDE([Revenue], [Orders])
Marketing Spend = SUM(cohort_mart[spend])
New Customers = SUM(cohort_mart[new_customers])
CAC = DIVIDE([Marketing Spend], [New Customers])
ROAS = DIVIDE([Revenue], [Marketing Spend])
Refund Rate = DIVIDE(SUM(cohort_mart[refund_count]), [Orders])
Net Revenue = [Revenue] - SUM(cohort_mart[refund_amount])
Payment Failure Rate = DIVIDE(SUM(cohort_mart[payment_failures]), SUM(cohort_mart[payment_attempts]))
Churn = DIVIDE(SUM(cohort_mart[churned]), SUM(cohort_mart[active_start]))
Retention Per Subscriber Day = 1 - [Churn]
Support Ticket Rate = DIVIDE(SUM(cohort_mart[tickets]), [Orders])
Gross Margin = 1 - DIVIDE(SUM(cohort_mart[cost]), [Revenue])
Repeat Purchase Rate = DIVIDE(SUM(cohort_mart[repeat_orders]), [Orders])
Active Customers = CALCULATE(DISTINCTCOUNT(fact_orders[customer_id]), fact_orders[status] = "PAID")
Paid Order Revenue = CALCULATE(SUM(fact_orders[amount]), fact_orders[status] = "PAID")
Active Critical Incidents = CALCULATE(COUNTROWS(incidents), incidents[severity] = "CRITICAL", incidents[status] <> "CLOSED")
Approval Rate = DIVIDE(CALCULATE(COUNTROWS(approvals), approvals[status] = "APPROVED"), CALCULATE(COUNTROWS(approvals), approvals[status] IN {"APPROVED", "REJECTED"}))
Recommendation Success Rate = DIVIDE(CALCULATE(COUNTROWS(outcomes), outcomes[outcome] = "SUCCESS"), COUNTROWS(outcomes))
Average Actual Impact = AVERAGE(actual_impacts[percentage_impact])
Expected Impact Error = AVERAGEX(actual_impacts, ABS(actual_impacts[difference_from_expected]))
Workflow Success Rate = DIVIDE(CALCULATE(COUNTROWS(pipeline_runs), pipeline_runs[status] = "SUCCESS"), CALCULATE(COUNTROWS(pipeline_runs), pipeline_runs[status] IN {"SUCCESS", "FAILED"}))
Data Quality Failure Rate = DIVIDE(CALCULATE(COUNTROWS(data_quality_results), data_quality_results[status] = "FAIL"), COUNTROWS(data_quality_results))
Revenue At Risk 7d = IF(HASONEVALUE(forecasts[incident_id]), CALCULATE(SUM(forecasts[exposure]), forecasts[metric] = "revenue", forecasts[horizon] <= 7))
Revenue At Risk 30d = IF(HASONEVALUE(forecasts[incident_id]), CALCULATE(SUM(forecasts[exposure]), forecasts[metric] = "revenue", forecasts[horizon] <= 30))
```

Format rates as percentages, EUR measures as currency, durations as minutes, and
missing denominators as blanks. Use confidence bounds in tooltips. Do not label a
heuristic anomaly score as the probability that an incident is real.

Use Conversion Trusted on executive cards and daily trend charts, together with
Tracking Coverage. The raw Conversion measure is for source reconciliation only.
Long-period coverage can conceal individual missing days; always inspect daily
quality warnings before interpreting an aggregate conversion measure.

For observatory charts, select one metric, dimension_name, dimension_value and grain.
Use `actual_value` and `expected_value` without summing incompatible scopes. Relative
variance is `(actual_value-expected_value)/expected_value`; a blank expected value
means insufficient historical baseline, not zero expected performance.
