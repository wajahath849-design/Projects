# Data dictionary

Generated from `src/common/models.py`. All records are synthetic.

Orders/payments/refunds are transactions. Sessions, campaigns, support, subscriptions and
application events are daily country-device-channel cohort summaries. Product category and
customer segment are cohort attributes. Customers are a registered pool; new customers means
first observed purchasers. Amounts are EUR; naive timestamps represent UTC.
Simulation dates label source time; created_at/updated_at label processing time.

## audit.api_requests

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| request_id | VARCHAR | False |  |
| method | VARCHAR | False |  |
| path | VARCHAR | False |  |
| status_code | INTEGER | False |  |
| duration_ms | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## audit.model_runs

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| model_name | VARCHAR | False |  |
| run_id | VARCHAR | False |  |
| parameters | JSON | False |  |
| result | JSON | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## audit.workflow_runs

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| workflow_name | VARCHAR | False |  |
| run_id | VARCHAR | False |  |
| status | VARCHAR | False |  |
| details | JSON | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## monitoring.anomalies

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| metric | VARCHAR | False |  |
| timestamp | DATETIME | False |  |
| dimension_name | VARCHAR | False |  |
| dimension_value | VARCHAR | False |  |
| actual | FLOAT | False |  |
| expected | FLOAT | False |  |
| deviation | FLOAT | False |  |
| method | JSON | False |  |
| anomaly_score | FLOAT | False |  |
| severity | VARCHAR | False |  |
| confidence | FLOAT | False |  |
| data_quality_status | VARCHAR | False |  |
| classification | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## monitoring.data_quality_results

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| run_id | VARCHAR | False |  |
| dataset | VARCHAR | False |  |
| check_type | VARCHAR | False |  |
| status | VARCHAR | False |  |
| severity | VARCHAR | False |  |
| details | JSON | False |  |
| column_name | VARCHAR | True |  |
| expected_value | VARCHAR | True |  |
| actual_value | VARCHAR | True |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## monitoring.metric_observations

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| metric_id | VARCHAR | False |  |
| timestamp | DATETIME | False |  |
| dimension_name | VARCHAR | False |  |
| dimension_value | VARCHAR | False |  |
| actual_value | FLOAT | True |  |
| baseline_value | FLOAT | True |  |
| expected_value | FLOAT | True |  |
| deviation_absolute | FLOAT | True |  |
| deviation_percent | FLOAT | True |  |
| grain | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## monitoring.pipeline_runs

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| workflow_name | VARCHAR | False |  |
| start_time | DATETIME | False |  |
| end_time | DATETIME | True |  |
| status | VARCHAR | False |  |
| rows_processed | INTEGER | False |  |
| error_message | TEXT | True |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.customers

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| country | VARCHAR | False |  |
| customer_segment | VARCHAR | False |  |
| acquired_at | DATETIME | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.deployments

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| timestamp | DATETIME | False |  |
| country | VARCHAR | False |  |
| device | VARCHAR | False |  |
| release | VARCHAR | False |  |
| component | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.operational_incidents

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| timestamp | DATETIME | False |  |
| country | VARCHAR | False |  |
| component | VARCHAR | False |  |
| description | VARCHAR | False |  |
| status | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.products

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| product_category | VARCHAR | False |  |
| price | FLOAT | False |  |
| unit_cost | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.web_sessions

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| timestamp | DATETIME | False |  |
| country | VARCHAR | False |  |
| device | VARCHAR | False |  |
| channel | VARCHAR | False |  |
| product_category | VARCHAR | False |  |
| customer_segment | VARCHAR | False |  |
| sessions | INTEGER | False |  |
| server_sessions | INTEGER | False |  |
| planned_promotion | INTEGER | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## simulation.simulation_ground_truth

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_type | VARCHAR | False |  |
| start_time | DATETIME | False |  |
| end_time | DATETIME | False |  |
| affected_country | VARCHAR | False |  |
| affected_device | VARCHAR | False |  |
| affected_channel | VARCHAR | False |  |
| affected_product | VARCHAR | False |  |
| expected_metric_effect | JSON | False |  |
| true_driver | VARCHAR | False |  |
| severity | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.incidents

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| anomaly_id | VARCHAR | True | monitoring.anomalies.id |
| detected_at | DATETIME | False |  |
| metric | VARCHAR | False |  |
| problem | TEXT | False |  |
| severity | VARCHAR | False |  |
| dimension_name | VARCHAR | False |  |
| dimension_value | VARCHAR | False |  |
| driver | VARCHAR | False |  |
| status | VARCHAR | False |  |
| closed_at | DATETIME | True |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.application_events

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| cohort_id | VARCHAR | False | raw.web_sessions.id |
| checkout_errors | INTEGER | False |  |
| attempts | INTEGER | False |  |
| latency_ms | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.marketing_campaigns

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| cohort_id | VARCHAR | False | raw.web_sessions.id |
| campaign | VARCHAR | False |  |
| spend | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.orders

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| cohort_id | VARCHAR | False | raw.web_sessions.id |
| customer_id | VARCHAR | False | raw.customers.id |
| product_id | VARCHAR | False | raw.products.id |
| timestamp | DATETIME | False |  |
| amount | FLOAT | False |  |
| cost | FLOAT | False |  |
| status | VARCHAR | False |  |
| is_new | INTEGER | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.subscriptions

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| cohort_id | VARCHAR | False | raw.web_sessions.id |
| active_start | INTEGER | False |  |
| churned | INTEGER | False |  |
| new_subscriptions | INTEGER | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.support_tickets

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| cohort_id | VARCHAR | False | raw.web_sessions.id |
| tickets | INTEGER | False |  |
| csat | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.evidence

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_id | VARCHAR | False | decision.incidents.id |
| evidence_type | VARCHAR | False |  |
| dimension | VARCHAR | False |  |
| segment | VARCHAR | False |  |
| metric | VARCHAR | False |  |
| current_value | FLOAT | False |  |
| baseline_value | FLOAT | False |  |
| difference | FLOAT | False |  |
| contribution | FLOAT | False |  |
| statistical_strength | FLOAT | False |  |
| description | TEXT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.hypotheses

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_id | VARCHAR | False | decision.incidents.id |
| driver | VARCHAR | False |  |
| description | TEXT | False |  |
| confidence | FLOAT | False |  |
| signals | JSON | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.lessons

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_id | VARCHAR | False | decision.incidents.id |
| lesson | TEXT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.recommendations

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_id | VARCHAR | False | decision.incidents.id |
| recommendation_type | VARCHAR | False |  |
| description | TEXT | False |  |
| supporting_evidence | JSON | False |  |
| confidence | FLOAT | False |  |
| expected_impact | FLOAT | False |  |
| risk_level | VARCHAR | False |  |
| requires_approval | INTEGER | False |  |
| memory_context | JSON | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## monitoring.forecasts

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| incident_id | VARCHAR | True | decision.incidents.id |
| metric | VARCHAR | False |  |
| timestamp | DATETIME | False |  |
| horizon | INTEGER | False |  |
| expected | FLOAT | False |  |
| lower | FLOAT | False |  |
| upper | FLOAT | False |  |
| exposure | FLOAT | False |  |
| method | VARCHAR | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.payments

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| order_id | VARCHAR | False | raw.orders.id |
| provider | VARCHAR | False |  |
| status | VARCHAR | False |  |
| amount | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## raw.refunds

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| order_id | VARCHAR | False | raw.orders.id |
| timestamp | DATETIME | False |  |
| amount | FLOAT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.actions

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| recommendation_id | VARCHAR | False | decision.recommendations.id |
| action_type | VARCHAR | False |  |
| status | VARCHAR | False |  |
| execution_time | DATETIME | False |  |
| effective_at | DATETIME | False |  |
| request_payload | JSON | False |  |
| response_payload | JSON | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.approvals

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| recommendation_id | VARCHAR | False | decision.recommendations.id |
| status | VARCHAR | False |  |
| expires_at | DATETIME | False |  |
| approved_by | VARCHAR | True |  |
| approved_at | DATETIME | True |  |
| rejection_reason | TEXT | True |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.expected_impacts

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| recommendation_id | VARCHAR | False | decision.recommendations.id |
| metric | VARCHAR | False |  |
| expected_percent | FLOAT | False |  |
| window_days | INTEGER | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.actual_impacts

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| action_id | VARCHAR | False | decision.actions.id |
| absolute_impact | FLOAT | False |  |
| percentage_impact | FLOAT | False |  |
| difference_from_expected | FLOAT | False |  |
| lower | FLOAT | False |  |
| upper | FLOAT | False |  |
| confidence | FLOAT | False |  |
| method | VARCHAR | False |  |
| pre_start | DATETIME | False |  |
| post_end | DATETIME | False |  |
| sample_size | INTEGER | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |

## decision.outcomes

| Column | Type | Nullable | Reference |
|---|---|---|---|
| id | VARCHAR | False | Primary key |
| action_id | VARCHAR | False | decision.actions.id |
| outcome | VARCHAR | False |  |
| description | TEXT | False |  |
| created_at | DATETIME | False |  |
| updated_at | DATETIME | False |  |
