import numpy as np


def measure(pre, post, control_pre, control_post, expected_percent: float, seed=42) -> dict:
    """Paired day-block bootstrap of difference in differences.

    Equal-length consecutive seven-day windows pair weekdays. Assumes an unaffected
    control with parallel trends and no other treatment-specific changes. Synthetic
    replay does not establish real-world causal effectiveness.
    """
    arrays = [np.asarray(x, dtype=float) for x in [pre, post, control_pre, control_post]]
    if len({len(x) for x in arrays}) != 1 or len(arrays[0]) < 7:
        raise ValueError("At least seven aligned daily observations per group and window are required")
    if not all(np.isfinite(x).all() for x in arrays):
        raise ValueError("Impact windows must contain finite values")
    pre, post, control_pre, control_post = arrays
    if pre.mean() <= 0 or control_pre.mean() <= 0:
        raise ValueError("Positive baseline required for relative effect")
    scale = pre.mean()/control_pre.mean()
    changes = (post-pre)-scale*(control_post-control_pre)
    absolute = float(changes.mean())
    rng = np.random.default_rng(seed)
    samples = rng.choice(changes, size=(2000, len(changes)), replace=True).mean(axis=1)
    lower, upper = np.quantile(samples, [.025, .975])/pre.mean()
    effect = absolute/pre.mean()
    if upper < 0:
        outcome = "NEGATIVE"
    elif lower <= 0 <= upper:
        outcome = "NO_EFFECT" if max(abs(lower), abs(upper)) < .02 else "INCONCLUSIVE"
    elif effect >= expected_percent*.8:
        outcome = "SUCCESS"
    else:
        outcome = "PARTIAL_SUCCESS"
    return dict(absolute_impact=absolute, percentage_impact=float(effect),
                difference_from_expected=float(effect-expected_percent), lower=float(lower), upper=float(upper),
                confidence=.95, sample_size=len(pre), method="paired_day_bootstrap_scaled_difference_in_differences",
                outcome=outcome)
