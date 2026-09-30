# Methodology

The original model evaluation uses GBP features. The dashboard's EUR reporting and campaign historical values use transaction-date ECB conversions described in [currency methodology](currency_methodology.md). Conversion preserves customer counts, retention, and model predictions; value-weighted shares and campaign ordering are recomputed in EUR.

## Analytical population

The commercial population includes valid catalogue merchandise with a positive unit price. Positive quantities are sales and negative quantities are recorded returns. Non-catalogue codes such as postage, bank charges, manual adjustments, and gift vouchers are outside the merchandise population. Exact duplicates across all eight original fields are removed with the first row retained.

Valid anonymous transactions remain in commercial totals. Customer retention and modeling require a customer identifier and therefore use a smaller, explicitly identified population.

Main commercial reporting covers 1 December 2010 through 30 November 2011. The source ends on 9 December 2011, so that partial month is excluded from comparisons.

## Retention

A customer's cohort is the calendar month of their first observed valid positive purchase. Retention at age month *k* is the number of original cohort customers purchasing in that calendar month divided by the cohort size. Only mature cells are generated. Because history before the dataset is unavailable, cohort entry is not necessarily true acquisition.

## Prediction target

At each monthly cutoff, the binary target is at least one valid positive purchase in `[cutoff, cutoff + 30 days)`. Features use transactions strictly before the cutoff. Customer ID is an entity key and is excluded from predictors.

Features include recency, tenure, 30- and 90-day order counts, prior-30-day orders, 90-day spend, active purchase days, historical order value, and a UK indicator. Positive-valued features are log-transformed before modeling.

## Temporal evaluation

- April–August cutoffs: training snapshots
- 1 September: candidate model selection by average precision
- 1 October: probability calibration, recency-baseline rate estimation, and fitting the three-feature logistic RFM baseline
- 1 November: untouched final evaluation
- 1–30 November: fully observed outcome window

Candidate models are regularized logistic regression and histogram gradient boosting. The selected model is calibrated with logistic scaling on the independent October population.

## Metrics

Average precision is primary because campaign capacity makes ranking positive customers more useful than raw accuracy. ROC AUC measures ordering across thresholds. Brier score evaluates probability accuracy. Precision, recall, and lift at the top 20% connect ranking performance to a contact constraint.

Paired customer bootstrap resampling produces 95% intervals for ROC AUC, average precision, and the average-precision difference against recency and RFM. These intervals do not represent uncertainty across seasons, retailers, or campaign treatments. RFM is fit on October so it is a recent operational benchmark; this is not a controlled comparison of algorithms trained on identical rows.

## Campaign scenario

The dashboard ranks customers with:

```text
capped historical order value × (1 − predicted purchase probability)
```

Historical order value is capped at the training-period 95th percentile. For an assumed absolute uplift `u`, incremental orders per customer are capped at `min(u, 1 − p)`. Assumed incremental contribution is:

```text
Σ [incremental probability × capped order value × margin] − contact cost
```

This is a sensitivity calculation. No treatment assignment, causal effect, true margin, or observed campaign cost exists in the source.
