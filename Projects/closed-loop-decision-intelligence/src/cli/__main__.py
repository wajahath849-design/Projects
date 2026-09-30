import argparse
import json

from sqlalchemy import select

from api.services.analytics import transform
from api.services.decisions import verify_impact
from api.services.orchestration import advance_simulation, run_pipeline
from src.common import models as m
from src.common.config import ROOT, offline_url
from src.common.db import make_engine
from src.common.logging import configure_logging
from src.common.store import initialize, records
from src.decision_engine.service import approve, execute
from src.decision_memory.service import ledger
from src.ingestion.loader import ingest
from src.synthetic_data.generator import generate


def main():
    parser = argparse.ArgumentParser(description="Closed-loop analytics; all actions are simulated")
    parser.add_argument("--offline", action="store_true", help="Explicit SQLite rehearsal; does not validate PostgreSQL or n8n")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    gen = sub.add_parser("generate-data")
    gen.add_argument("--months", type=int, default=24)
    gen.add_argument("--seed", type=int, default=42)
    gen.add_argument("--csv", action="store_true")
    sub.add_parser("run-pipeline")
    sub.add_parser("transform")
    demo = sub.add_parser("demo")
    demo.add_argument("--approve-simulation", action="store_true",
                      help="Explicitly authorize the local simulated rollback; default prompts interactively")
    demo.add_argument("--actor", default="local-demo-operator")
    sub.add_parser("evaluate")
    sub.add_parser("ledger")
    sub.add_parser("operations")
    args = parser.parse_args()
    configure_logging()
    (ROOT / "data/generated").mkdir(parents=True, exist_ok=True)
    engine = make_engine(offline_url() if args.offline else None)
    initialize(engine)
    result = {"status": "initialized", "dialect": engine.dialect.name}
    if args.command == "generate-data":
        frames, truth = generate(args.months, args.seed)
        result = ingest(engine, frames, truth, ROOT / "data/generated/csv" if args.csv else None)
    elif args.command == "run-pipeline":
        result = run_pipeline(engine)
    elif args.command == "transform":
        result = transform(engine)
    elif args.command == "demo":
        result = demo_run(engine, args.approve_simulation, args.actor)
    elif args.command == "evaluate":
        from src.evaluation.report import evaluate
        result = evaluate(engine)
    elif args.command == "ledger":
        with engine.connect() as connection:
            result = ledger(connection)
    elif args.command == "operations":
        from api.services.operations import operating_metrics
        with engine.connect() as connection:
            result = operating_metrics(connection)
    print(json.dumps(result, indent=2, default=str))


def demo_run(engine, approval_granted=False, actor="local-demo-operator") -> dict:
    with engine.connect() as connection:
        populated = connection.execute(select(m.web_sessions.c.id).limit(1)).first()
    if not populated:
        frames, truth = generate()
        ingest(engine, frames, truth)
    with engine.connect() as connection:
        prepared = connection.execute(select(m.recommendations.c.id).limit(1)).first()
    if not prepared:
        run_pipeline(engine)
    with engine.connect() as connection:
        candidates = records(connection, m.recommendations, m.recommendations.c.recommendation_type == "ROLLBACK")
        if not candidates:
            raise RuntimeError("No evidence-backed rollback was detected; demo cannot fabricate an incident")
        recommendation = sorted(candidates, key=lambda r: r["confidence"], reverse=True)[0]
    print(json.dumps({"human_review": recommendation}, indent=2, default=str))
    if not approval_granted:
        approval_granted = input("Approve this simulated rollback? Type APPROVE: ").strip() == "APPROVE"
    if not approval_granted:
        with engine.begin() as connection:
            approve(connection, recommendation["id"], actor, False, "Demo operator declined")
        return {"status": "REJECTED", "action_executed": False}
    with engine.begin() as connection:
        approve(connection, recommendation["id"], actor, True)
        action = execute(connection, recommendation["id"])
    advance_simulation(engine, action["id"])
    impact = verify_impact(engine, action["id"])
    with engine.connect() as connection:
        row = next(r for r in ledger(connection) if r["incident_id"] == recommendation["incident_id"])
    export = ROOT / "data/exports/demo_ledger.json"
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_text(json.dumps(row, indent=2, default=str), encoding="utf-8")
    return {"impact": impact, "ledger": row, "export": str(export)}


if __name__ == "__main__":
    main()
