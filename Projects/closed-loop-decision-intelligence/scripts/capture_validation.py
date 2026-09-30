"""Capture real persisted outputs for repository samples, without approval or action."""
import json

from sqlalchemy import func, select

from api.services.operations import operating_metrics
from src.common import models as m
from src.common.config import ROOT, offline_url
from src.common.db import make_engine
from src.common.store import initialize, records
from src.decision_memory.service import ledger

engine = make_engine(offline_url())
initialize(engine)
with engine.connect() as connection:
    counts = {str(t.fullname): connection.scalar(select(func.count()).select_from(t)) for t in m.metadata.sorted_tables}
    entries = ledger(connection)
    completed = [r for r in entries if r["closed_at"] is not None]
    if not completed:
        raise RuntimeError("No completed ledger entry exists; refusing to invent a sample")
    row = completed[0]
    evidence = records(connection, m.evidence, m.evidence.c.incident_id == row["incident_id"])
    ops = operating_metrics(connection)
for name, content in [("demo_ledger.json", row), ("warehouse_counts.json", counts),
                      ("demo_evidence.json", evidence), ("operational_kpis.json", ops)]:
    (ROOT/"data/samples"/name).write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
    if name == "demo_ledger.json":
        (ROOT/"data/exports"/name).write_text(json.dumps(content, indent=2, default=str), encoding="utf-8")
print(json.dumps({"table_counts": counts, "completed_ledger_rows": len(completed)}, indent=2))
