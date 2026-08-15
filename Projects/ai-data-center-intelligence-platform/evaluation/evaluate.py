from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.database import discover_schema
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator
from src.sql_validator import SQLValidator


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    security_cases = json.loads((ROOT / "evaluation/security_tests.json").read_text(encoding="utf-8"))
    validator = SQLValidator(discover_schema(ROOT / "database/datacenter.db"))
    security_results = []
    for case in security_cases:
        result = validator.validate(case["input"])
        observed = "allowed" if result.valid else "blocked"
        security_results.append({**case, "observed": observed, "passed": observed == case["expected"]})

    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    ground_truth = json.loads((ROOT / "evaluation/ground_truth.json").read_text(encoding="utf-8"))
    questions = {item["id"]: item for item in json.loads((ROOT / "evaluation/questions.json").read_text(encoding="utf-8"))}
    offline_results = []
    for truth in ground_truth:
        result = pipeline.ask(questions[truth["id"]]["question"])
        offline_results.append({
            "id": truth["id"], "status": result.status, "sql_executed": result.status == "ok",
            "row_count": 0 if result.frame is None else len(result.frame), "execution_ms": result.execution_ms,
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "offline verified-example baseline; not full Ollama accuracy",
        "security_cases": len(security_results),
        "security_passed": sum(item["passed"] for item in security_results),
        "offline_sql_cases": len(offline_results),
        "offline_sql_executed": sum(item["sql_executed"] for item in offline_results),
        "security_results": security_results,
        "offline_results": offline_results,
    }
    target = ROOT / "evaluation/results/offline_baseline.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if not key.endswith("results")}, indent=2))


if __name__ == "__main__":
    main()
