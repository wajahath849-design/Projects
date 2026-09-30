WITH customers AS (SELECT CAST(timestamp AS date) AS date, COUNT(DISTINCT customer_id) AS active_customers
 FROM {{ ref('stg_orders') }} WHERE status='PAID' GROUP BY CAST(timestamp AS date))
SELECT CAST(m.timestamp AS date) AS date,
  SUM(m.revenue) AS revenue,
  SUM(m.orders) AS orders,
  1.0 * SUM(m.orders) / NULLIF(SUM(m.sessions), 0) AS conversion,
  1.0 * SUM(m.revenue) / NULLIF(SUM(m.orders), 0) AS aov,
  1.0 * SUM(m.spend) / NULLIF(SUM(m.new_customers), 0) AS cac,
  1.0 * SUM(m.revenue) / NULLIF(SUM(m.spend), 0) AS roas,
  1.0 * SUM(m.refund_count) / NULLIF(SUM(m.orders), 0) AS refund_rate,
  1.0 * SUM(m.payment_failures) / NULLIF(SUM(m.payment_attempts), 0) AS payment_failure_rate,
  1.0 * SUM(m.churned) / NULLIF(SUM(m.active_start), 0) AS churn,
  1.0 - (1.0 * SUM(m.churned) / NULLIF(SUM(m.active_start), 0)) AS retention,
  1.0 * SUM(m.tickets) / NULLIF(SUM(m.orders), 0) AS support_ticket_rate,
  1.0 - (1.0 * SUM(m.cost) / NULLIF(SUM(m.revenue), 0)) AS gross_margin,
  MAX(c.active_customers) AS active_customers,
  SUM(m.new_customers) AS new_customers,
  1.0 * SUM(m.repeat_orders) / NULLIF(SUM(m.orders), 0) AS repeat_purchase_rate,
  SUM(m.sessions) AS traffic,
  SUM(m.tickets) AS support_volume,
  1.0 * SUM(m.checkout_errors) / NULLIF(SUM(m.attempts), 0) AS checkout_error_rate,
  SUM(m.spend) AS spend
FROM {{ ref('cohort_mart') }} m LEFT JOIN customers c ON c.date=CAST(m.timestamp AS date)
GROUP BY CAST(m.timestamp AS date)
