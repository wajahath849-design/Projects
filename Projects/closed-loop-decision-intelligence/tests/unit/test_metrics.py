import pandas as pd
import pytest

from src.metrics.engine import Metric, aggregate


def test_weighted_ratio_and_zero_denominator():
    metric = Metric(metric_id="conversion", name="Conversion", description="Paid/session", owner="growth",
                    aggregation="ratio", numerator="orders", denominator="sessions", direction="up")
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-01"]*2+["2026-01-02"]),
                          "orders": [1, 9, 0], "sessions": [2, 98, 0]})
    result = aggregate(frame, metric)
    assert result.actual_value.iloc[0] == pytest.approx(.1)
    assert pd.isna(result.actual_value.iloc[1])


def test_distinct_customers_are_not_summed_across_cohorts():
    metric = Metric(metric_id="active_customers", name="Active", description="Unique purchasers", owner="Growth",
                    aggregation="distinct_count", numerator="active_customers", direction="up")
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2026-01-01", "2026-01-01"]),
                          "active_customers": [2, 2], "_customer_ids": [frozenset(["a", "b"]), frozenset(["b", "c"])]})
    assert aggregate(frame, metric).actual_value.iloc[0] == 3
