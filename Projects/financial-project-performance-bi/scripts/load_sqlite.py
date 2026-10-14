"""Optional SQLite copy for SQL portfolio exercises and audit queries."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.utils.common import ROOT, path_from_config


def load(db_path: Path | None = None) -> Path:
    db_path = db_path or ROOT / "data/staging/financial_bi.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for path in sorted(path_from_config("curated_dir").glob("*.csv")):
            if path.stem == "ProjectMetrics":
                continue
            pd.read_csv(path).to_sql(path.stem, conn, if_exists="replace", index=False)
        conn.executescript((ROOT / "sql/schemas/create.sql").read_text(encoding="utf-8"))
        conn.executescript((ROOT / "sql/views/project_financials.sql").read_text(encoding="utf-8"))
        conn.commit()
    return db_path


if __name__ == "__main__":
    print(load())
