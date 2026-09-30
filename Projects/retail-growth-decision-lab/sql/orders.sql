-- One invoice per known customer. These are gross merchandise orders: return
-- transactions stay in line_items and are never guessed back onto sales.
-- All source dates are retained here to support explicit model cutoffs.
SELECT customer_id,
       invoice_no,
       MIN(invoice_date) AS invoice_date,
       MIN(country) AS country,
       SUM(line_revenue) AS revenue,
       SUM(quantity) AS quantity
FROM line_items
WHERE kind = 'sale' AND customer_id IS NOT NULL
GROUP BY customer_id, invoice_no
ORDER BY invoice_date, invoice_no, customer_id;
