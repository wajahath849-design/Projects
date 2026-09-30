SELECT country,
       SUM(line_revenue) AS gross_sales,
       COUNT(DISTINCT invoice_no) AS orders,
       COUNT(DISTINCT customer_id) AS customers
FROM line_items
WHERE kind = 'sale' AND invoice_date >= :period_start AND invoice_date < :period_end
GROUP BY country
ORDER BY gross_sales DESC, country;
