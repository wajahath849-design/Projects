# Retail Growth Decision Lab — executive brief

## Decision

Use the calibrated gradient-boosting model to create the ranking frame for a controlled customer-outreach experiment. Do not treat propensity scores as incremental campaign response.

## Evidence

The reviewed complete-month period contains €10.76M net merchandise revenue, 18,957 positive orders, and 4,293 identified customers. Recorded returns represent 3.16% of gross merchandise sales. November was the strongest complete month at €1.66M, although the source does not establish what caused that increase. Monetary amounts are translated from original GBP using transaction-date ECB reference rates, with the latest prior published rate on non-publication days.

On the untouched November prediction window, 33.7% of known customers purchased. The model achieved 0.626 average precision, compared with 0.600 for a strong RFM baseline and 0.419 for recency alone. Contacting the model's highest-ranked 20% would have captured 39.1% of observed purchasers, compared with 37.5% under RFM and 24.8% under recency. The model's top group had 65.9% observed precision and 1.96× lift over the population rate. The paired bootstrap interval for average-precision improvement over RFM was 0.016–0.037.

## Operating proposal

Choose a feasible contact capacity, stratify customers by score and recency segment, then randomize eligible customers between treatment and control. Pre-register conversion, incremental contribution, contact cost, and guardrails. The campaign simulator is useful for sensitivity planning; it is not evidence of achieved impact.

## Risks

The evidence covers one historical retailer and one final test month. The data provides revenue rather than contribution profit and lacks campaign assignments. First-observed-purchase cohorts may include existing customers whose earlier history is not recorded. Bootstrap intervals capture customer variation inside November, not uncertainty across time or markets.
