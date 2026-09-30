import pandas as pd
import pytest
from pipeline.currency import translate


def test_division_direction_prior_rate_and_returns():
    lines = pd.DataFrame({"invoice_date": ["2011-01-07", "2011-01-09", "2011-01-10"],
                          "line_revenue": [80., -40., 90.]})
    rates = pd.DataFrame({"rate_date": pd.to_datetime(["2011-01-07", "2011-01-10"]), "gbp_per_eur": [.8, .9]})
    result = translate(lines, rates)
    assert list(result.line_revenue) == [100., -50., 100.]
    assert result.iloc[1].rate_date == pd.Timestamp("2011-01-07")
    assert list(result.line_revenue_gbp) == [80., -40., 90.]


def test_missing_history_does_not_use_future_rate():
    lines = pd.DataFrame({"invoice_date": ["2011-01-01"], "line_revenue": [80.]})
    rates = pd.DataFrame({"rate_date": pd.to_datetime(["2011-01-02"]), "gbp_per_eur": [.8]})
    with pytest.raises(ValueError, match="Missing or stale"):
        translate(lines, rates)


def test_stale_rates_fail_instead_of_silently_filling():
    lines = pd.DataFrame({"invoice_date": ["2011-01-10"], "line_revenue": [80.]})
    rates = pd.DataFrame({"rate_date": pd.to_datetime(["2011-01-01"]), "gbp_per_eur": [.8]})
    with pytest.raises(ValueError, match="Missing or stale"):
        translate(lines, rates)
