import json
import sqlite3
from pathlib import Path

import pandas as pd

from src.anomaly_detection import AnomalyDetector


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"
AUDIT = PROJECT_ROOT / "evaluation" / "results" / "anomaly_detection_phase10.json"
SUPPORTED_METRICS = {
    "pue", "power_draw_kw", "cooling_power_kw", "cooling_cost",
    "cpu_utilization_pct", "memory_utilization_pct", "disk_utilization_pct",
    "network_utilization_pct", "latency_ms", "packet_loss_pct",
    "downtime_minutes", "incident_count",
}


def test_detector_loads_all_required_metrics() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        observations = AnomalyDetector(connection).load_observations()
    assert set(observations["metric_name"]) == SUPPORTED_METRICS
    assert len(observations) == 242_664


def test_stored_anomalies_are_outside_documented_bounds() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        frame = pd.read_sql_query("SELECT * FROM detected_anomalies", connection)
    assert len(frame) == 893
    assert set(frame["method"]) == {"seasonal_iqr"}
    assert (
        ((frame["direction"] == "high") & (frame["observed_value"] > frame["upper_bound"]))
        | ((frame["direction"] == "low") & (frame["observed_value"] < frame["lower_bound"]))
    ).all()
    assert set(frame["severity"]) <= {"medium", "high", "critical"}


def test_method_comparison_is_persisted() -> None:
    report = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert report["selected_method"] == "seasonal_iqr"
    assert set(report["supported_metrics"]) == SUPPORTED_METRICS
    assert {item["method"] for item in report["method_comparison"]} == {
        "global_zscore", "global_iqr", "seasonal_iqr",
    }
    assert report["integrity_check"] == "ok"
    assert report["foreign_key_violations"] == 0


def test_anomaly_ids_and_output_are_deterministic() -> None:
    with sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True) as connection:
        detector = AnomalyDetector(connection)
        regenerated = detector.detect(detector.load_observations())
        stored = pd.read_sql_query(
            "SELECT anomaly_id, timestamp, facility_id, metric_name FROM detected_anomalies ORDER BY anomaly_id",
            connection,
        )
    pd.testing.assert_frame_equal(
        regenerated[["anomaly_id", "timestamp", "facility_id", "metric_name"]],
        stored,
    )
