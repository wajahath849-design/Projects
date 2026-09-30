-- Commercial totals include anonymous shoppers. Net sales book observed
-- negative merchandise lines in their own month, not the original sale month.
SELECT SUBSTR(invoice_date, 1, 7) AS month,
       SUM(CASE WHEN kind = 'sale' THEN line_revenue ELSE 0 END) AS gross_sales,
       -SUM(CASE WHEN kind = 'return' THEN line_revenue ELSE 0 END) AS returns_value,
       SUM(line_revenue) AS net_sales,
       COUNT(DISTINCT CASE WHEN kind = 'sale' THEN invoice_no END) AS orders,
       COUNT(DISTINCT CASE WHEN kind = 'sale' THEN customer_id END) AS customers
FROM line_items
WHERE kind IN ('sale', 'return')
  AND invoice_date >= :period_start AND invoice_date < :period_end
GROUP BY SUBSTR(invoice_date, 1, 7)
ORDER BY month;
