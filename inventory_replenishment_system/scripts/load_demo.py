from __future__ import annotations

import json
from pathlib import Path

from app.db import SessionLocal
from app.ingestion import ingest_dataset
from app.pipeline import run_full_pipeline


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    with SessionLocal() as session:
        results = [
            ingest_dataset(session, "transactions", ROOT / "sample_data" / "transactions.csv"),
            ingest_dataset(session, "snapshots", ROOT / "sample_data" / "snapshots.csv"),
            ingest_dataset(session, "lead_times", ROOT / "sample_data" / "lead_times.csv"),
        ]
        session.commit()
    print(json.dumps({"ingestion": results}, indent=2, default=str))
    print(json.dumps(run_full_pipeline(), indent=2, default=str))


if __name__ == "__main__":
    main()
