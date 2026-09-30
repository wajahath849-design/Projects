# Synthetic incident evaluation

Computed from persisted observations and isolated ground truth.

- evaluation_unit: precision/FPR: global metric-day alerts; recall: episodes across all monitored scopes
- total_simulated_incidents: 6
- detected_incidents: 6
- true_positive_alerts: 45
- false_positive_alerts: 2
- precision: 0.9574468085106383
- all_scope_alert_precision: 0.9300947867298578
- all_scope_true_positive_alerts: 785
- all_scope_false_positive_alerts: 59
- recall: 1.0
- false_positive_rate: 0.0003641660597232338
- negative_metric_days: 5492
- mean_detection_delay_hours: 0.0
- driver_identification_accuracy: 1.0
- severity_exact_match_accuracy: 1.0

| Episode | Driver | Detected | Driver identified |
|---|---|---|---|
| 001 | deployment | True | True |
| 002 | campaign_efficiency | True | True |
| 003 | inventory | True | True |
| 004 | support | True | True |
| 005 | payment_provider | True | True |
| 006 | tracking | True | True |

Single synthetic seed is a smoke evaluation, not external validation.
Daily aggregation cannot resolve minute-level detection delay.
Global alert precision counts repeated days; all-scope recall counts distinct hidden episodes.
Development-seed evaluation; scope policy was revised after inspecting missed inventory coverage.
Observational evidence supports hypotheses, not causal identification.
