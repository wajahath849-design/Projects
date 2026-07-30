from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.ingestion import ingest_dataset
from app.jobs import enqueue_job
from app.pipeline import run_full_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory replenishment administration CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest a CSV file")
    ingest_parser.add_argument("dataset_type", choices=["transactions", "snapshots", "lead_times"])
    ingest_parser.add_argument("file_path")

    run_parser = subparsers.add_parser("run", help="Run forecasting and replenishment now")
    run_parser.add_argument("--horizon-days", type=int, default=None)

    job_parser = subparsers.add_parser("enqueue", help="Queue a background pipeline job")
    job_parser.add_argument("job_type", choices=["FULL_PIPELINE", "FORECAST", "REPLENISHMENT", "INGEST_CSV", "OVERRIDE_RECALC", "INGEST_DOCUMENT", "INGEST_EXTERNAL_SIGNAL"])
    job_parser.add_argument("--payload", default="{}", help="JSON object")
    job_parser.add_argument("--requested-by", required=True)
    job_parser.add_argument("--priority", type=int, default=100)

    args = parser.parse_args()
    if args.command == "ingest":
        with SessionLocal() as session:
            result = ingest_dataset(session, args.dataset_type, Path(args.file_path))
            session.commit()
        print(json.dumps(result, indent=2, default=str))
        return 0
    if args.command == "run":
        print(json.dumps(run_full_pipeline(args.horizon_days), indent=2, default=str))
        return 0
    if args.command == "enqueue":
        payload = json.loads(args.payload)
        if not isinstance(payload, dict):
            raise ValueError("--payload must be a JSON object")
        with SessionLocal() as session:
            job_id = enqueue_job(session, args.job_type, payload, args.requested_by, args.priority)
        print(json.dumps({"job_id": str(job_id), "status": "QUEUED"}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
