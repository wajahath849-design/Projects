-- First OBSERVED purchase cohorts, not proven acquisition cohorts: the source
-- contains no pre-December-2010 purchase history. Generate only mature cells.
WITH RECURSIVE
customer_first AS (
    SELECT customer_id, MIN(SUBSTR(invoice_date, 1, 7)) AS cohort
    FROM orders WHERE invoice_date < :period_end GROUP BY customer_id
),
cohort_sizes AS (
    SELECT cohort, COUNT(*) AS cohort_size FROM customer_first GROUP BY cohort
),
ages(age_month) AS (
    SELECT 0 UNION ALL SELECT age_month + 1 FROM ages WHERE age_month < 120
),
mature_grid AS (
    SELECT s.cohort, a.age_month, s.cohort_size,
           STRFTIME('%Y-%m', DATE(s.cohort || '-01', '+' || a.age_month || ' months')) AS activity_month
    FROM cohort_sizes s CROSS JOIN ages a
    WHERE DATE(s.cohort || '-01', '+' || a.age_month || ' months') < DATE(:period_end)
),
activity AS (
    SELECT f.cohort, SUBSTR(o.invoice_date, 1, 7) AS activity_month,
           COUNT(DISTINCT o.customer_id) AS customers
    FROM orders o JOIN customer_first f USING (customer_id)
    WHERE o.invoice_date < :period_end
    GROUP BY f.cohort, SUBSTR(o.invoice_date, 1, 7)
)
SELECT g.cohort, g.age_month, COALESCE(a.customers, 0) AS customers,
       g.cohort_size, 1.0 * COALESCE(a.customers, 0) / g.cohort_size AS retention
FROM mature_grid g LEFT JOIN activity a
  ON g.cohort = a.cohort AND g.activity_month = a.activity_month
ORDER BY g.cohort, g.age_month;
