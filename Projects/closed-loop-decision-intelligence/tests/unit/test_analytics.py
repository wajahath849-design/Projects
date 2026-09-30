import numpy as np
import pandas as pd
import pytest

from src.anomaly_detection.detector import count_tail, detect
from src.forecasting.engine import forecast
from src.impact.statistics import measure
from src.investigation.engine import contributions


def test_impact_controls_common_trend():
    before = np.ones(7)*100
    result = measure(before, before*1.15, before, before*1.05, .1)
    assert result["percentage_impact"] == pytest.approx(.1)
    assert result["outcome"] == "SUCCESS"
    assert measure(before, before*.8, before, before, .1)["outcome"] == "NEGATIVE"
    with pytest.raises(ValueError):
        measure([1], [2], [1], [1], .1)


def test_forecast_has_ordered_intervals():
    f = forecast(100+10*np.sin(np.arange(84)*2*np.pi/7), 30)
    assert len(f["expected"]) == 30
    assert all(lo <= mid <= hi for lo, mid, hi in zip(f["lower"], f["expected"], f["upper"]))


def test_forecast_quality_gap_keeps_weekday_alignment():
    values = 100+10*np.sin(np.arange(84)*2*np.pi/7)
    values[42:44] = np.nan
    result = forecast(values)
    assert result["training_rows"] == 84
    assert result["imputed_rows"] == 2


def test_contributions_reconcile_per_dimension():
    rows = []
    for day in pd.date_range("2026-01-01", periods=57):
        for country, value in [("Germany", 100), ("France", 50)]:
            rows.append(dict(timestamp=day, country=country, country_device=country+" / Mobile", device="Mobile",
                channel="Direct", product_category="Software", customer_segment="Consumer", campaign="Direct",
                revenue=value*(.5 if day == pd.Timestamp("2026-02-26") and country == "Germany" else 1)))
    evidence = contributions(pd.DataFrame(rows), "2026-02-26")
    germany = next(e for e in evidence if e["dimension"] == "country" and e["segment"] == "Germany")
    assert germany["difference"] == -50
    assert germany["contribution"] == 1


def test_constant_series_does_not_alert():
    dates = pd.date_range("2026-01-01", periods=90)
    obs = pd.DataFrame(dict(timestamp=dates, metric_id="revenue", dimension_name="all", dimension_value="all",
                            actual_value=100., expected_value=100.))
    assert detect(obs, set()) == []
    obs.loc[89, "actual_value"] = 30
    assert detect(obs, set())[0]["metric"] == "revenue"


def test_sparse_rate_doubling_is_not_strong_evidence():
    p = count_tail("payment_failure_rate", .04, .02,
                   {"payment_failures": 2, "payment_attempts": 50}, 1400, .02)
    assert p > .01
    p = count_tail("payment_failure_rate", .4, .02,
                   {"payment_failures": 40, "payment_attempts": 100}, 2800, .02)
    assert p < .0001
