"""Deterministic, template-based explanation text without an LLM dependency."""

from __future__ import annotations

FEATURE_LABELS = {
    "lag_1": "yesterday's demand",
    "lag_7": "demand seven days ago",
    "lag_14": "demand fourteen days ago",
    "rolling_mean_7": "the recent seven-day demand average",
    "rolling_mean_14": "the recent fourteen-day demand average",
    "rolling_std_7": "recent demand variability",
    "current_price": "the current price",
    "promotion_proxy": "the promotion indicator",
    "current_stock": "current stock",
    "stockout_flag": "the stockout-risk indicator",
    "day_of_week": "the day of week",
    "weekend_flag": "the weekend indicator",
}


def explanation_text(feature: str, value: object, contribution: float) -> str:
    """Render a factual direction statement from a feature contribution."""
    label = FEATURE_LABELS.get(feature, feature.replace("_", " "))
    direction = (
        "increased" if contribution > 0
        else "decreased" if contribution < 0
        else "did not change"
    )
    return (
        f"{label.capitalize()} ({value}) {direction} the forecast by "
        f"{abs(contribution):.3f} units relative to the model baseline."
    )
