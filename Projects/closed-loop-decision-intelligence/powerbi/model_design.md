# Semantic model

| Table | Grain / key | Relationships / use |
|---|---|---|
| analytics.dim_date | Calendar day / date | One-to-many to fact and observation Date columns |
| analytics.dim_customer | Customer / id | Customer → fact_orders.customer_id |
| analytics.dim_product | Product / id | Product → fact_orders.product_id |
| analytics.dim_country | Country name | Country → fact_sessions.country |
| analytics.dim_channel | Channel name | Channel → fact_sessions.channel |
| analytics.fact_sessions | Daily country-device-channel cohort / id | One-to-many to orders.cohort_id; filter propagation to orders |
| analytics.fact_orders | Checkout order / id | One-to-one to fact_payments.order_id |
| analytics.fact_marketing | Cohort allocation / id | Sessions → marketing.cohort_id |
| analytics.fact_support | Cohort support summary / id | Sessions → support.cohort_id |
| analytics.cohort_mart | Daily cohort / id | Alternative aggregate star; do not relate to transaction facts |
| monitoring.metric_observations | Metric × date × scope × grain / id | Disconnected KPI trend table; enforce one metric, scope and grain |
| monitoring.anomalies | Metric × date × scope / id | Anomalies → incidents.anomaly_id |
| monitoring.forecasts | Incident × metric × horizon / id | Incidents → forecasts.incident_id |
| decision.incidents | Coalesced global metric episode / id | Parent for evidence, hypotheses, recommendation |
| decision.evidence | Incident × dimension × segment / id | Incidents → evidence.incident_id |
| decision.recommendations | One per incident / id | Incidents → recommendations.incident_id |
| decision.approvals | One per recommendation / id | Recommendations → approvals.recommendation_id |
| decision.actions | One per recommendation / id | Recommendations → actions.recommendation_id |
| decision.actual_impacts | One per action / id | Actions → actual_impacts.action_id |
| decision.outcomes | One per measured action / id | Actions → outcomes.action_id |
| decision.v_decision_ledger | Incident chain, one row per incident | Disconnected detail table; drillthrough by incident_id |
| monitoring.data_quality_results | Check execution / id | Quality page; filter to latest run per dataset |
| monitoring.pipeline_runs | Python stage execution / id | System operation page |
| audit.workflow_runs | Durable stage audit / id | Do not add to pipeline counts: same runs |

Use either the cohort mart for additive business KPIs or the transaction star for
customer distinct counts and payment-provider drilldowns. **Never sum active-customer
counts across cohorts or time.** Active Customers is DISTINCTCOUNT over paid orders.
Conversion is SUM(paid orders)/SUM(sessions); AOV, CAC, ROAS and margins are ratios of
sums. Subscriber snapshots define subscriber-day churn; monthly cohort retention
requires a separate cohort model and is not represented by this rate.

All amounts are synthetic EUR, including United Kingdom sales. Refund amounts are
same-day in this simulator. Gross revenue and margin exclude tax and refund effects;
use Net Revenue when analyzing refund-adjusted receipts. Support and subscriptions
are cohort summaries, not individual CRM-ticket/subscriber event histories.

Forecasts are per incident and share dates. Select one incident before summing risk,
otherwise overlapping incidents double count exposure. The observed-decline exposure
assumes persistence; it is a scenario, not a forecasted probability of loss.

Use a read-only PostgreSQL role for Power BI, restricted to analytics, monitoring and
decision views. Do not import `simulation.simulation_ground_truth` into the report.
Keep raw PII out of published reports; this synthetic dataset has no real PII.
