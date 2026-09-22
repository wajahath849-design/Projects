# Audit methodology

Metric Mirage audits ratio metrics of the form:

```text
metric = SUM(numerator) / SUM(denominator)
```

Examples include conversion rate, defect rate, click-through rate and renewal rate.

The claim text supplies context for the review. It is not parsed into a hypothesis or checked for causal meaning. Baseline observations occur before the split date; current observations occur on or after it. If no split is supplied, the engine chooses the middle distinct valid date, taking the later middle date for an even count.

## Checks

### Input integrity

The engine counts exact duplicates, unparseable dates, missing numeric values and non-positive denominators. Dates and numeric fields are parsed before calculation. Invalid dates, missing calculation values, negative numerators and non-positive denominators are excluded. Exact duplicates are flagged but retained: the engine cannot infer whether a repeated record is legitimate. Quality issue counts can overlap within the same row; `valid_rows` is the actual number of included observations.

### Segment reversal

For each value in the first selected segment column, Metric Mirage compares its baseline and current rates. At least two groups present in both periods are required; otherwise the segment and fixed-mix checks return `not_applicable`, shown as **Not assessed** in the interface. Additional selected columns are recorded in the contract but are not analyzed.

A high-severity reversal is raised when the aggregate direction is non-zero and every comparable segment moves in the opposite direction. If only some segments oppose the aggregate, the consistency check is marked for review without declaring a complete reversal.

### Population mix normalization

Current segment rates are reweighted using baseline denominator shares:

```text
adjusted_current = Σ baseline_share(segment) × current_rate(segment)
```

This answers: “What would the current metric be if the population composition had not changed?” It is descriptive normalization, not a causal counterfactual. Only groups found in both periods are included; their denominator shares are renormalized within that overlap. Missing groups can limit how well the adjusted result represents the full population.

### Composition drift

The engine calculates total variation distance between the baseline and current denominator shares of comparable groups. A distance of 0 means identical composition. Distances of at least 0.10 create a medium-severity finding; at least 0.30 creates a high-severity finding. Because shares are renormalized over common groups, this calculation does not measure the contribution of groups that appear or disappear entirely.

### Statistical reliability

A pooled two-proportion z-test is available only when each row contains integer success and trial counts, successes do not exceed trials, and each period has at least five expected successes and five expected failures under the pooled rate. Unsupported ratios or smaller samples return **Not assessed**.

The test assumes independent binary outcomes. Repeated users, clustered events and temporal dependence can invalidate that assumption. A two-sided p-value of at least 0.05 triggers a review finding; a smaller p-value is not proof of a meaningful effect or that the claim is true. The test does not control for seasonality or confounding.

### Outlier resistance

The comparison is recalculated after excluding denominator values below the 1st or above the 99th percentile. A finding is raised when the absolute difference between the trimmed and original changes exceeds the larger of 30% of the original absolute change or 0.005 ratio units (0.5 percentage points for a proportion). If trimming empties either comparison period, the check is **Not assessed**. This check concerns denominator weights, not every form of outlier.

## Evidence score and coverage

The score begins at 100 and subtracts transparent penalties:

| Severity | Penalty |
|---|---:|
| Critical | 28 |
| High | 22 |
| Medium | 12 |
| Low | 6 |

The result is bounded at zero. This is a heuristic summary of detected issues, not a calibrated probability, statistical confidence level or model accuracy measure. Related findings can overlap. A check can be marked for review without producing a separate scored finding.

Skipped checks do not subtract penalties and do not validate an assumption. `methodology.tests_run` counts applicable checks; `tests_available` records the total offered. Read coverage alongside the score. The API retains the field name `confidence_score` for compatibility, while the interface calls it **Evidence score**.

## Traceable results

Each result includes a `contract` with source and calculation columns, primary and additional segments, split date, actual observed comparison ranges and column count. `limitations` records relevant caveats. The JSON evidence download retains this complete result. The printable decision report presents a shorter summary of the claim, findings, recommendations and scope.

## Responsible interpretation

- Automated findings identify risks; they do not establish causality.
- Segment selection must be justified before analysis.
- Multiple exploratory comparisons can increase false discoveries.
- The current release does not replace randomized experiments.
- No language model performs calculations or changes the result.
