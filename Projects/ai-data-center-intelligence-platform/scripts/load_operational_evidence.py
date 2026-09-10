"""Load generated operational evidence into the existing SQLite database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


TABLES = ("system_logs", "alerts", "maintenance_actions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("database/datacenter.db"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--schema", type=Path, default=Path("database/operational_evidence.sql"))
    parser.add_argument("--audit", type=Path, default=Path("evaluation/results/operational_evidence_load.json"))
    args = parser.parse_args()

    connection = sqlite3.connect(args.database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(args.schema.read_text(encoding="utf-8"))
        connection.execute("BEGIN IMMEDIATE")
        for table in reversed(TABLES):
            connection.execute(f'DELETE FROM "{table}"')
        for table in TABLES:
            frame = pd.read_csv(args.data_dir / f"{table}.csv")
            frame.to_sql(table, connection, if_exists="append", index=False, method="multi", chunksize=500)
        connection.commit()
        connection.execute("ANALYZE")
        connection.execute("PRAGMA optimize")
        connection.commit()
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in TABLES}
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "integrity_check": integrity,
        "foreign_key_violations": foreign_keys,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
