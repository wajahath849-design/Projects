WITH totals AS (
  SELECT SUM(revenue) AS mart FROM {{ ref('cohort_mart') }}
), source AS (
  SELECT SUM(amount) AS raw FROM {{ ref('stg_orders') }} WHERE status='PAID'
)
SELECT * FROM totals CROSS JOIN source WHERE ABS(mart - raw) > 0.01
