from pathlib import Path

from sqlalchemy import func, select

from src.common import models as m
from src.common.store import upsert


def ingest(engine, frames: dict, truth: list[dict] | None = None, csv_dir: Path | None = None) -> dict:
    """Atomically insert deterministic source IDs. Existing datasets require a fresh DB.

    Refusing mixed simulation runs prevents silently merging different seeds or horizons.
    Evaluation ground truth is written only by this simulation ingestion boundary.
    """
    with engine.begin() as connection:
        if connection.scalar(select(func.count()).select_from(m.web_sessions)):
            raise ValueError("Source data already exists; use a fresh database for another simulation")
        counts = {}
        for target in m.RAW_TABLES:
            rows = frames[target.name].to_dict("records")
            counts[target.name] = upsert(connection, target, rows)
        if truth:
            upsert(connection, m.simulation_ground_truth, truth)
    if csv_dir:
        csv_dir.mkdir(parents=True, exist_ok=True)
        for name, frame in frames.items():
            frame.to_csv(csv_dir / f"{name}.csv", index=False)
    return counts
