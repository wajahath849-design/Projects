"""Generate and transactionally store server risk and facility health scores."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk_scoring import OperationsScoreEngine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--schema", type=Path, default=Path("database/advanced_analytics.sql"))
    parser.add_argument("--weights", type=Path, default=Path("analytics/health_score_weights.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/results/operations_scores_phases15_16.json"))
    args = parser.parse_args()
    connection = sqlite3.connect(args.database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        output = OperationsScoreEngine(connection, args.weights).score()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        output.server_risk.to_csv(args.output_dir / "server_failure_risk.csv", index=False)
        output.facility_health.to_csv(args.output_dir / "facility_health_scores.csv", index=False)
        connection.executescript(args.schema.read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM incident_reviews")
        connection.execute("DELETE FROM server_failure_risk")
        connection.execute("DELETE FROM facility_health_scores")
        reviews = pd.read_csv(args.output_dir / "incident_reviews.csv")
        reviews.to_sql("incident_reviews", connection, if_exists="append", index=False, method="multi", chunksize=100)
        output.server_risk.to_sql("server_failure_risk", connection, if_exists="append", index=False, method="multi", chunksize=200)
        output.facility_health.to_sql("facility_health_scores", connection, if_exists="append", index=False, method="multi", chunksize=100)
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
        **output.metadata,
        "server_risk_rows": len(output.server_risk),
        "risk_levels": output.server_risk.groupby("risk_level").size().sort_index().to_dict(),
        "facility_health_rows": len(output.facility_health),
        "health_ranking": output.facility_health.sort_values("health_score", ascending=False)[
            ["facility_id", "health_score"]
        ].to_dict("records"),
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
        "caveat": "Risk and health scores are transparent synthetic-data triage indicators, not guaranteed failures or safety certifications.",
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
