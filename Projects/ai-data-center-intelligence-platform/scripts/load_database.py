"""Build the SQLite analytical database atomically from canonical processed CSVs."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk_scoring import OperationsScoreEngine


LOAD_ORDER = (
    "facilities",
    "servers",
    "server_metrics",
    "power_metrics",
    "network_metrics",
    "uptime_incidents",
    "system_logs",
    "alerts",
    "maintenance_actions",
    "detected_anomalies",
    "incident_reviews",
)

DERIVED_SCORE_TABLES = ("server_failure_risk", "facility_health_scores")
DERIVED_OPERATIONAL_TABLES = (
    "agg_facility_monthly_operations", "agg_event_code_monthly",
)


def load_csv(connection: sqlite3.Connection, csv_path: Path, table: str) -> int:
    row_count = 0
    for chunk in pd.read_csv(csv_path, chunksize=100_000, low_memory=False):
        chunk.to_sql(table, connection, if_exists="append", index=False, method="multi", chunksize=500)
        row_count += len(chunk)
    return row_count


def validate_database(connection: sqlite3.Connection) -> dict[str, object]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    counts = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in LOAD_ORDER + DERIVED_SCORE_TABLES + DERIVED_OPERATIONAL_TABLES
    }
    views = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name"
        )
    ]
    indexes = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {
        "integrity_check": integrity,
        "foreign_key_violations": len(foreign_keys),
        "row_counts": counts,
        "views": views,
        "indexes": indexes,
    }


def build_database(
    data_dir: Path,
    database_path: Path,
    schema_path: Path,
    views_path: Path,
    aggregates_path: Path,
    evidence_schema_path: Path,
    advanced_schema_path: Path,
    operational_aggregates_path: Path,
) -> dict[str, object]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = database_path.with_suffix(database_path.suffix + ".building")
    temporary_path.unlink(missing_ok=True)

    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        connection.executescript(evidence_schema_path.read_text(encoding="utf-8"))
        connection.executescript(advanced_schema_path.read_text(encoding="utf-8"))
        loaded = {}
        with connection:
            for table in LOAD_ORDER:
                loaded[table] = load_csv(connection, data_dir / f"{table}.csv", table)
        connection.executescript(views_path.read_text(encoding="utf-8"))
        connection.executescript(aggregates_path.read_text(encoding="utf-8"))
        connection.executescript(operational_aggregates_path.read_text(encoding="utf-8"))
        score_output = OperationsScoreEngine(
            connection, PROJECT_ROOT / "analytics/health_score_weights.yaml"
        ).score()
        score_output.server_risk.to_sql(
            "server_failure_risk", connection, if_exists="append", index=False,
            method="multi", chunksize=200,
        )
        score_output.facility_health.to_sql(
            "facility_health_scores", connection, if_exists="append", index=False,
            method="multi", chunksize=100,
        )
        score_output.server_risk.to_csv(data_dir / "server_failure_risk.csv", index=False)
        score_output.facility_health.to_csv(data_dir / "facility_health_scores.csv", index=False)
        loaded["server_failure_risk"] = len(score_output.server_risk)
        loaded["facility_health_scores"] = len(score_output.facility_health)
        for table in DERIVED_OPERATIONAL_TABLES:
            loaded[table] = connection.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]
        connection.execute("ANALYZE")
        validation = validate_database(connection)
        if validation["integrity_check"] != "ok" or validation["foreign_key_violations"]:
            raise RuntimeError(f"Database validation failed: {validation}")
        connection.execute("PRAGMA optimize")
        connection.commit()
    finally:
        connection.close()

    os.replace(temporary_path, database_path)
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_directory": data_dir.as_posix(),
        "database_path": database_path.as_posix(),
        "loaded_rows": loaded,
        "validation": validation,
        "database_bytes": database_path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical SQLite database.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--schema", type=Path, default=Path("database/schema.sql"))
    parser.add_argument("--views", type=Path, default=Path("database/views.sql"))
    parser.add_argument("--aggregates", type=Path, default=Path("database/aggregates.sql"))
    parser.add_argument(
        "--evidence-schema",
        type=Path,
        default=Path("database/operational_evidence.sql"),
    )
    parser.add_argument(
        "--advanced-schema",
        type=Path,
        default=Path("database/advanced_analytics.sql"),
    )
    parser.add_argument(
        "--operational-aggregates",
        type=Path,
        default=Path("database/operational_aggregates.sql"),
    )
    parser.add_argument("--audit", type=Path, default=Path("docs/step5_database_audit.json"))
    args = parser.parse_args()
    audit = build_database(
        args.data_dir,
        args.database,
        args.schema,
        args.views,
        args.aggregates,
        args.evidence_schema,
        args.advanced_schema,
        args.operational_aggregates,
    )
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit["validation"], indent=2))


if __name__ == "__main__":
    main()
