# Historical EUR reporting

The UCI workbook records unit prices in GBP. The dashboard reports EUR by translating each retained sale and return before aggregation.

**Rate source:** European Central Bank daily euro reference rates. ECB quotes pounds per euro, so `EUR amount = GBP amount / GBP-per-EUR rate`. The rate date is the transaction's recorded calendar date. On non-publication days, the latest prior reference date is used; rates from future days are never used. The maximum observed gap is two days. Same-day rates are used for retrospective reporting and are not claimed to have been available before each intraday transaction.

The bounded ECB extract and its SHA-256 fingerprint are versioned in `data/fx/`. The date mapping records which rate each transaction date used. The pipeline fails on missing, non-positive, duplicate, or more-than-seven-day-old rates. No rounding occurs at the line level; dashboard displays are rounded independently of calculations.

## Commercial reporting

Both positive sales and negative returns use the date on which the source recorded them. The project does not infer an original purchase for a return. All country, month, customer-mix, and summary revenue measures are rebuilt from the translated ledger. Counts and retention are unchanged. Revenue-weighted shares and month-over-month changes may differ from GBP results because the daily rates vary.

## Model and campaign values

The fitted model and its features remain in GBP, preserving the original temporal evaluation. Purchase probabilities and model metrics are unchanged. The campaign's historical order value and 90-day spend are recomputed from EUR-translated historical orders. The EUR order-value cap is the training-snapshot 95th percentile, €1,076.19. The scenario then ranks value × (1 − purchase probability), so the priority ordering can differ from the original GBP demonstration. All campaign budget and contact-cost inputs are EUR; exports explicitly include `currency=EUR`.

The 30-day purchase probability is not causal uplift. Scenario contribution still depends on assumed margin and assumed incremental purchase probability. At default settings, €1,000 funds 1,000 contacts and produces a hypothetical €6,955 contribution after contact cost. This is not an observed campaign outcome.

## Reproduce

Run `python -m pipeline.currency` after ingestion, analytics, and model scoring, or use `python -m pipeline.run`. Original GBP outputs remain available beside the EUR outputs for reconciliation. The source models and raw workbook are never overwritten by currency conversion.

[ECB rate source](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) · [UCI source](https://doi.org/10.24432/C5BW33)
