import json
import sqlite3
from pathlib import Path

import pandas as pd
import yaml

from src.risk_scoring import OperationsScoreEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"
WEIGHTS = PROJECT_ROOT / "analytics" / "health_score_weights.yaml"


def test_health_weights_are_governed_and_sum_to_one() -> None:
    config = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))
    assert config["version"] == "1.0.0"
    assert abs(sum(config["weights"].values()) - 1.0) < 1e-9
    assert len(config["weights"]) == 6


def test_score_engine_covers_every_server_and_facility() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        output = OperationsScoreEngine(connection, WEIGHTS).score()
    assert len(output.server_risk) == 430
    assert output.server_risk["server_id"].nunique() == 430
    assert len(output.facility_health) == 6
    assert output.facility_health["facility_id"].nunique() == 6


def test_risk_scores_are_explainable_and_cautious() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        frame = pd.read_sql_query("SELECT * FROM server_failure_risk", connection)
    assert frame["risk_score"].between(0, 100).all()
    assert set(frame["risk_level"]) <= {"low", "moderate", "high", "critical"}
    assert set(frame["forecast_horizon_days"]) == {7}
    assert set(frame["lookback_days"]) == {365}
    assert frame["recommendation"].str.startswith(("Inspect", "Review")).all()
    assert frame["recommendation"].str.lower().str.contains("guarantee").sum() == 0
    assert all(isinstance(json.loads(value), dict) for value in frame["signal_summary_json"])


def test_health_score_reconciles_to_fixed_weighted_components() -> None:
    config = yaml.safe_load(WEIGHTS.read_text(encoding="utf-8"))
    weights = config["weights"]
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        frame = pd.read_sql_query("SELECT * FROM facility_health_scores", connection)
    expected = (
        frame["energy_efficiency_score"] * weights["energy_efficiency"]
        + frame["reliability_score"] * weights["reliability"]
        + frame["network_health_score"] * weights["network_health"]
        + frame["infrastructure_utilization_score"] * weights["infrastructure_utilization"]
        + frame["incident_severity_score"] * weights["incident_severity"]
        + frame["anomaly_frequency_score"] * weights["anomaly_frequency"]
    ).round(2)
    pd.testing.assert_series_equal(frame["health_score"], expected, check_names=False)
    numeric_scores = [
        "health_score", "energy_efficiency_score", "reliability_score",
        "network_health_score", "infrastructure_utilization_score",
        "incident_severity_score", "anomaly_frequency_score",
    ]
    assert frame[numeric_scores].apply(lambda column: column.between(0, 100).all()).all()
    assert set(frame["weights_version"]) == {"1.0.0"}
