"""Generated-data regressions: detectors never receive the hidden scenario registry."""
import pandas as pd
import pytest

from src.anomaly_detection.detector import detect
from src.data_quality.guardian import validate
from src.metrics.engine import observations
from src.synthetic_data.generator import generate


@pytest.fixture(scope="module")
def sources():
    frames, _hidden = generate(12, seed=42)
    return frames


def lightweight_mart(frames):
    """Independent pandas oracle for a subset of the SQL mart, for detector testing."""
    sessions = frames["web_sessions"].copy()
    paid = frames["orders"][frames["orders"].status == "PAID"]
    totals = paid.groupby("cohort_id").agg(revenue=("amount", "sum"), orders=("id", "size"))
    cube = sessions.merge(totals, left_on="id", right_index=True, how="left").fillna({"revenue": 0, "orders": 0})
    cube["country_device"] = cube.country + " / " + cube.device
    return cube


def test_generated_checkout_and_tracking_incidents(sources, monkeypatch):
    from src.metrics.engine import registry
    metrics = [m for m in registry() if m.metric_id in ("revenue", "orders", "conversion", "traffic")]
    monkeypatch.setattr("src.metrics.engine.registry", lambda: metrics)
    cube = lightweight_mart(sources)
    quality = validate(sources)
    assert not quality.quarantined
    assert len(quality.tracking_days) == 6
    obs = observations(cube, dimensions=["all", "country_device"])
    anomalies = detect(obs, quality.tracking_days, frame=cube)
    last_week = cube.timestamp.max().normalize()-pd.Timedelta(days=6)
    checkout = [a for a in anomalies if a["dimension_value"] == "Germany / Mobile"
                and a["metric"] == "conversion" and pd.Timestamp(a["timestamp"]) >= last_week]
    assert checkout, "The generated Germany mobile checkout failure must be detected"
    tracking = [a for a in anomalies if a["classification"] == "DATA_QUALITY"]
    assert tracking and all(a["metric"] == "traffic" for a in tracking)
    assert not [a for a in anomalies if a["metric"] == "conversion"
                and pd.Timestamp(a["timestamp"]).normalize() in quality.tracking_days]
    # On the observed tracking outage, transactional orders remain near the previous week.
    daily = cube.groupby(cube.timestamp.dt.normalize()).orders.sum()
    assert all(.7 < daily.loc[d]/daily.loc[d-pd.Timedelta(days=7)] < 1.3 for d in quality.tracking_days)


def test_corrupt_source_is_quarantined(sources):
    broken = {name: frame for name, frame in sources.items()}
    broken["orders"] = pd.concat([sources["orders"], sources["orders"].iloc[:1]], ignore_index=True)
    assert validate(broken).quarantined
    broken["orders"] = sources["orders"].drop(columns="amount")
    assert validate(broken).quarantined
