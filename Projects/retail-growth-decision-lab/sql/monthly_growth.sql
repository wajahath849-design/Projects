-- Executed growth bridge with a window function. New/returning revenue uses
-- known IDs only; gross_sales and net_sales above retain anonymous shoppers.
WITH first_purchase AS (
    SELECT customer_id, MIN(SUBSTR(invoice_date, 1, 7)) AS first_month
    FROM orders GROUP BY customer_id
),
customer_mix AS (
    SELECT SUBSTR(o.invoice_date, 1, 7) AS month,
           SUM(CASE WHEN SUBSTR(o.invoice_date, 1, 7) = f.first_month THEN o.revenue ELSE 0 END) AS first_observed_customer_revenue,
           SUM(CASE WHEN SUBSTR(o.invoice_date, 1, 7) > f.first_month THEN o.revenue ELSE 0 END) AS returning_customer_revenue
    FROM orders o JOIN first_purchase f USING (customer_id)
    WHERE o.invoice_date >= :period_start AND o.invoice_date < :period_end
    GROUP BY SUBSTR(o.invoice_date, 1, 7)
),
growth AS (
    SELECT month, gross_sales, returns_value, net_sales, orders, customers,
           LAG(net_sales) OVER (ORDER BY month) AS previous_month_net_sales
    FROM monthly
)
SELECT g.*, (g.net_sales - g.previous_month_net_sales) / NULLIF(g.previous_month_net_sales, 0) AS net_sales_mom,
       c.first_observed_customer_revenue, c.returning_customer_revenue,
       c.returning_customer_revenue / NULLIF(c.first_observed_customer_revenue + c.returning_customer_revenue, 0) AS returning_customer_revenue_share
FROM growth g LEFT JOIN customer_mix c USING (month)
ORDER BY month;
