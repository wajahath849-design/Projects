-- SQLAlchemy named parameters; bind :start_time and :end_time, never interpolate.
SELECT s.country, s.device, p.provider,
       COUNT(*) AS payment_attempts,
       SUM(CASE WHEN p.status = 'FAILED' THEN 1 ELSE 0 END) AS failures,
       SUM(CASE WHEN o.status = 'PAID' THEN o.amount ELSE 0 END) AS paid_revenue
FROM raw.orders o
JOIN raw.web_sessions s ON s.id = o.cohort_id
JOIN raw.payments p ON p.order_id = o.id
WHERE o.timestamp >= :start_time AND o.timestamp < :end_time
GROUP BY s.country, s.device, p.provider
ORDER BY failures DESC;
