WITH order_totals AS (
 SELECT cohort_id,
   SUM(CASE WHEN status='PAID' THEN amount ELSE 0 END) AS revenue,
   SUM(CASE WHEN status='PAID' THEN cost ELSE 0 END) AS cost,
   SUM(CASE WHEN status='PAID' THEN 1 ELSE 0 END) AS orders,
   COUNT(*) AS payment_attempts,
   SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS payment_failures,
   SUM(is_new) AS new_customers,
   SUM(CASE WHEN status='PAID' AND is_new=0 THEN 1 ELSE 0 END) AS repeat_orders,
   COUNT(DISTINCT CASE WHEN status='PAID' THEN customer_id END) AS active_customers
 FROM {{ ref('stg_orders') }} GROUP BY cohort_id
), refund_totals AS (
 SELECT o.cohort_id, COUNT(*) AS refund_count, SUM(r.amount) AS refund_amount
 FROM {{ ref('stg_refunds') }} r JOIN {{ ref('stg_orders') }} o ON o.id=r.order_id GROUP BY o.cohort_id
)
SELECT s.id, s.timestamp, s.country, s.device, s.channel, s.product_category,
 s.customer_segment, s.sessions, s.server_sessions, s.planned_promotion,
 COALESCE(o.revenue,0) AS revenue, COALESCE(o.cost,0) AS cost,
 COALESCE(o.orders,0) AS orders, COALESCE(o.payment_attempts,0) AS payment_attempts,
 COALESCE(o.payment_failures,0) AS payment_failures, COALESCE(o.new_customers,0) AS new_customers,
 COALESCE(o.repeat_orders,0) AS repeat_orders, COALESCE(o.active_customers,0) AS active_customers,
 COALESCE(r.refund_count,0) AS refund_count, COALESCE(r.refund_amount,0) AS refund_amount,
 c.spend, c.campaign, t.tickets, t.csat, u.active_start, u.churned, u.new_subscriptions,
 e.checkout_errors, e.attempts, e.latency_ms
FROM {{ ref('stg_web_sessions') }} s
LEFT JOIN order_totals o ON s.id=o.cohort_id
LEFT JOIN refund_totals r ON s.id=r.cohort_id
LEFT JOIN {{ ref('stg_marketing_campaigns') }} c ON s.id=c.cohort_id
LEFT JOIN {{ ref('stg_support_tickets') }} t ON s.id=t.cohort_id
LEFT JOIN {{ ref('stg_subscriptions') }} u ON s.id=u.cohort_id
LEFT JOIN {{ ref('stg_application_events') }} e ON s.id=e.cohort_id
