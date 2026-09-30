# Metric dictionary

Source: config/metrics.yaml and validated Metric defaults.

Ratios use summed components. Zero denominators yield missing values. Active Customers uses
distinct paying customer IDs at the selected grain, not a sum of cohort distinct counts.

| Metric | Definition | Owner | Adverse direction | Aggregation |
|---|---|---|---|---|
| revenue | Paid order gross revenue in EUR before refunds and tax | Finance | Decrease | sum |
| orders | Successfully paid orders | Commerce | Decrease | sum |
| conversion | Paid orders divided by tracked sessions | Growth | Decrease | ratio |
| aov | Gross revenue per paid order | Finance | Decrease | ratio |
| cac | Allocated marketing spend per first-time purchaser | Growth | Increase | ratio |
| roas | Attributed gross revenue per euro of allocated spend | Growth | Decrease | ratio |
| refund_rate | Same-day refunded orders per paid order | Commerce | Increase | ratio |
| payment_failure_rate | Failed payments per attempt | Payments | Increase | ratio |
| churn | Subscription exits per subscriber-day at risk | Customer Success | Increase | ratio |
| retention | One minus subscription exit rate per subscriber-day; not cohort retention | Customer Success | Decrease | ratio |
| support_ticket_rate | Support tickets per paid order | Support | Increase | ratio |
| gross_margin | One minus merchandise cost divided by gross revenue before refunds | Finance | Decrease | ratio |
| active_customers | Distinct paying customers in the selected period and scope | Growth | Decrease | distinct_count |
| new_customers | First observed purchasers; one acquisition globally per customer | Growth | Decrease | sum |
| repeat_purchase_rate | Orders after a customer's first purchase divided by paid orders | Growth | Decrease | ratio |
| traffic | Tracked web sessions | Growth | Decrease | sum |
| support_volume | Support tickets opened | Support | Increase | sum |
| checkout_error_rate | Application checkout errors per attempt | Engineering | Increase | ratio |
| spend | Allocated campaign spend in EUR | Growth | Increase | sum |

Defaults: daily monitoring; country/device/channel/product_category/customer_segment dimensions;
20% warning, 40% critical deviation; trailing same-weekday comparison. Thresholds are votes,
not standalone alert triggers. The ensemble and incident scope rules also apply.

Hourly grouping is supported but this generator supplies daily snapshots, not intraday history.
Churn and retention use subscriber-days, not cohort retention. Gross margin excludes refunds
and tax. ROAS is attributed revenue per allocated spend, not incremental marketing ROI.
