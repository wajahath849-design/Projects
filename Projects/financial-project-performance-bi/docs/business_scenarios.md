# Business scenarios — synthetic demonstration data

All figures use the validated curated facts and the same project metrics as the dashboard. Data is fictional; actions are examples for management discussion, not actual company outcomes.

## A. Confirmed over-budget project — P001

Approved budget $480,000.00; actual cost $661,837.47; unfavorable variance $181,837.47 (37.9% of budget).
The largest cost categories are Contractors $290,117.04, Employees $246,976.33, Procurement $85,811.81. January–September 2026 cost totals $362,742.44; this is where the spend rate accelerated. Review transactions T-P001-14-00 (2026-03-11, $5,345.39); T-P001-14-01 (2026-03-24, $5,172.65); T-P001-14-02 (2026-03-20, $5,000.17).
Management options: validate contractor scope and approvals, separate committed work from discretionary work, and rebaseline only after the commercial impact is approved.

## B. Declining profitability — P002

Q1 2026 recognized revenue $106,250.01 against cost $94,434.33, a 11.1% margin. Q3 recognized revenue $87,125.01 against cost $149,622.93, a -71.7% margin. Lifetime margin is -5.0%.
Since April 2026 the main cost contributors are Employees $135,175.16, Contractors $130,243.61, Travel $18,626.76. Example records: T-P002-15-02 (2026-04-12, $6,246.25); T-P002-19-00 (2026-08-05, $5,972.00); T-P002-17-01 (2026-06-23, $5,953.62). Both higher contractor costs and lower monthly recognition are visible in the synthetic source; this is a designed scenario, not a causal finding about a real business.
Management options: review contract milestones and revenue recognition evidence, renegotiate supplier rates, and assess remaining work against expected contribution.

## C. Forecasted overrun before the budget is breached — P003

Approved budget $800,000.00; actual cost $746,676.32; remaining approved budget $53,323.68. Base estimate to complete $97,260.51 gives forecast at completion $843,936.83 and expected overrun $43,936.83.
Recent cost evidence: Employees $38,339.75, Contractors $25,975.24, Procurement $13,988.77. Example records: T-P003-18-04 (2026-07-22, $4,283.59); T-P003-18-03 (2026-07-14, $3,746.59); T-P003-20-07 (2026-09-04, $3,690.73). The baseline extrapolates the trailing three months through the planned end date, so it is sensitive to staffing and schedule changes.
Management options: confirm remaining deliverables and resource plan, compare optimistic and downside scenarios, and seek change control before the forecast becomes an actual overrun.

## Reproduce

Run `python run_pipeline.py --regenerate` and then `python -m src.analytics.scenarios`. The source facts and scenario figures share the same calculation path.
