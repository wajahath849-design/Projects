SELECT id FROM {{ ref('cohort_mart') }}
WHERE revenue < 0 OR orders < 0 OR orders > payment_attempts
   OR payment_failures + orders <> payment_attempts
   OR churned > active_start OR refund_count > orders
   OR spend IS NULL OR sessions < 0
