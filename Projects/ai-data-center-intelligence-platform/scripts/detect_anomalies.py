"""Compare explainable anomaly methods and store the governed detector output."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.anomaly_detection import AnomalyDetector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--schema", type=Path, default=Path("database/advanced_analytics.sql"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/detected_anomalies.csv"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/results/anomaly_detection_phase10.json"))
    args = parser.parse_args()

    connection = sqlite3.connect(args.database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        detector = AnomalyDetector(connection)
        observations = detector.load_observations()
        comparisons = detector.compare_methods(observations)
        anomalies = detector.detect(observations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        anomalies.to_csv(args.output, index=False)
        connection.executescript(args.schema.read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM detected_anomalies")
        anomalies.to_sql(
            "detected_anomalies", connection, if_exists="append", index=False,
            method="multi", chunksize=500,
        )
        connection.commit()
        connection.execute("ANALYZE")
        connection.execute("PRAGMA optimize")
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "observation_count": len(observations),
        "selected_method": detector.SELECTED_METHOD,
        "supported_metrics": sorted(observations["metric_name"].unique().tolist()),
        "method_comparison": [comparison.__dict__ for comparison in comparisons],
        "anomaly_count": len(anomalies),
        "by_metric": anomalies.groupby("metric_name").size().sort_index().to_dict(),
        "by_severity": anomalies.groupby("severity").size().sort_index().to_dict(),
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "scope": "Facility-day metrics and facility-month incident metrics; synthetic historical observations.",
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
