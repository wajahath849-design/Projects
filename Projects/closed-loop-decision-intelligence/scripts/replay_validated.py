"""Re-run the original sources into a fresh DB after an analytical-policy revision.

Preserves the first rehearsal and its decision audit trail. Does not copy outcomes
or recommendations. Explicit simulator test approval is recorded under a test actor.
"""
import json

import pandas as pd
from sqlalchemy import select

from api.services.orchestration import run_pipeline
from src.cli.__main__ import demo_run
from src.common import models as m
from src.common.config import ROOT
from src.common.db import make_engine
from src.common.logging import configure_logging
from src.common.store import initialize, records
from src.evaluation.report import evaluate
from src.ingestion.loader import ingest

configure_logging()
source = make_engine("sqlite:///"+str(ROOT/"data/generated/offline.db"))
target = make_engine("sqlite:///"+str(ROOT/"data/generated/validated.db"))
initialize(target)
with source.connect() as connection:
    frames = {str(t.name): pd.read_sql(select(t).where(~t.c.id.like("replay-%")), connection)
              .drop(columns=["created_at", "updated_at"]) for t in m.RAW_TABLES}
    truth = [{k: v for k, v in r.items() if k not in ("created_at", "updated_at")}
             for r in records(connection, m.simulation_ground_truth)]
print(json.dumps(ingest(target, frames, truth)), flush=True)
del frames
print(json.dumps(run_pipeline(target), default=str), flush=True)
print(json.dumps(evaluate(target), default=str), flush=True)
print(json.dumps(demo_run(target, approval_granted=True, actor="automated-demo-validation"), default=str), flush=True)
