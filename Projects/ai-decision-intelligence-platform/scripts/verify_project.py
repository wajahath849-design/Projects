"""Run the end-to-end sample pipeline and every critical Phase 17 verification."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.database.connection import connect, fetch_scalar  # noqa: E402
from decision_intelligence.settings import load_settings  # noqa: E402

PIPELINE = (
    ("sample_generation", "generate_m5_sample.py", ()),
    ("sample_ingestion", "load_m5_data.py", ("--sample",)),
    ("enterprise_generation", "generate_enterprise_data.py", ("--sample",)),
    ("initial_quality", "run_data_quality.py", ()),
    ("feature_build", "build_features.py", ()),
    ("model_training", "train_models.py", ()),
    ("forecast_generation", "generate_forecasts.py", ()),
    ("explanation_generation", "generate_explanations.py", ()),
    ("inventory_intelligence", "calculate_inventory_intelligence.py", ()),
    ("optimization", "run_optimization.py", ()),
    ("scenario_simulation", "run_scenarios.py", ()),
    ("power_bi_export", "export_power_bi_data.py", ()),
    ("final_quality", "run_data_quality.py", ()),
)


def _run(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(
            f"{name} failed with exit code {result.returncode}\n{result.stdout}\n{result.stderr}"
        )
    print(f"[PASS] {name}")
    return {"name": name, "returncode": result.returncode}


def _database_checks() -> dict[str, int]:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        checks = {
            "production_models": int(fetch_scalar(
                connection, "SELECT COUNT(*) FROM dbo.DimModel WHERE IsProduction=1"
            )),
            "forecast_rows": int(fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM dbo.FactForecast WHERE DataVersion='phase-10-v1'",
            )),
            "explanation_rows": int(fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM dbo.FactModelExplanation WHERE DataVersion='phase-10-v1'",
            )),
            "inventory_risk_rows": int(fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM dbo.FactStockoutRisk WHERE DataVersion='phase-11-v1'",
            )),
            "recommendation_rows": int(fetch_scalar(
                connection,
                """SELECT COUNT(*) FROM dbo.FactOptimizationRecommendation
                WHERE DataVersion='phase-12-v1' AND SolverStatus IN ('OPTIMAL','FEASIBLE')""",
            )),
            "invalid_recommendations": int(fetch_scalar(
                connection,
                """SELECT COUNT(*) FROM dbo.FactOptimizationRecommendation
                WHERE DataVersion='phase-12-v1'
                  AND (RecommendedOrderQuantity<0 OR SolverStatus NOT IN ('OPTIMAL','FEASIBLE'))""",
            )),
            "scenario_rows": int(fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM dbo.FactScenarioResult WHERE DataVersion='phase-13-v1'",
            )),
            "power_bi_views": int(fetch_scalar(
                connection,
                "SELECT COUNT(*) FROM sys.views WHERE name LIKE 'vw_PBI[_]%'",
            )),
        }
        latest_run = fetch_scalar(
            connection,
            "SELECT TOP 1 PipelineRunID FROM dbo.FactDataQuality ORDER BY CreatedAt DESC",
        )
        checks["latest_quality_failures"] = int(fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactDataQuality WHERE PipelineRunID=? AND Status='FAIL'",
            latest_run,
        ))
        for view in (
            "vw_PBI_ExecutiveOverview", "vw_PBI_DemandForecast",
            "vw_PBI_InventoryIntelligence", "vw_PBI_OptimizationRecommendations",
            "vw_PBI_ScenarioComparison", "vw_PBI_ModelPerformance", "vw_PBI_DataQuality",
            "vw_PBI_ForecastExplanations",
        ):
            connection.execute(f"SELECT TOP 1 * FROM dbo.{view}").fetchone()
    expected = {
        "production_models": 1, "forecast_rows": 720, "explanation_rows": 3600,
        "inventory_risk_rows": 20, "invalid_recommendations": 0,
        "scenario_rows": 200, "power_bi_views": 8, "latest_quality_failures": 0,
    }
    for name, value in expected.items():
        if checks[name] != value:
            raise RuntimeError(f"Database check {name}: expected {value}, got {checks[name]}")
    if checks["recommendation_rows"] < 1:
        raise RuntimeError("No feasible optimization recommendations were stored")
    print("[PASS] database_model_optimization_scenario_powerbi")
    return checks


def _artifact_checks() -> dict[str, Any]:
    required_docs = (
        "architecture.md", "model_card.md", "data_dictionary.md", "api.md",
        "installation.md", "power_bi_guide.md", "interview_guide.md",
        "cv_description.md", "release_checklist.md",
    )
    missing = [name for name in required_docs if not (PROJECT_ROOT / "docs" / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing documentation: {missing}")
    selected = json.loads((
        PROJECT_ROOT / "models" / "metadata" / "selected_model.json"
    ).read_text(encoding="utf-8"))
    artifact_path = Path(selected["artifact_path"])
    if not artifact_path.is_absolute():
        artifact_path = PROJECT_ROOT / artifact_path
    if not artifact_path.is_file():
        raise RuntimeError("Selected model artifact is missing")
    diagnostics = json.loads((
        PROJECT_ROOT / "data" / "exports" / "optimization" / "diagnostics.json"
    ).read_text(encoding="utf-8"))
    if diagnostics["solver_status"] not in {"OPTIMAL", "FEASIBLE"}:
        raise RuntimeError("Optimization diagnostics do not contain a usable solution")
    manifest = json.loads((
        PROJECT_ROOT / "powerbi" / "exports" / "manifest.json"
    ).read_text(encoding="utf-8"))
    if len(manifest["views"]) != 8 or manifest["dax_measure_count"] < 31:
        raise RuntimeError("Power BI manifest is incomplete")
    from decision_intelligence.api.main import app

    required_api_paths = 17
    if len(app.openapi()["paths"]) < required_api_paths:
        raise RuntimeError("OpenAPI contract is missing required paths")
    print("[PASS] model_api_powerbi_documentation_artifacts")
    return {
        "selected_model": selected["model_id"],
        "solver_status": diagnostics["solver_status"],
        "power_bi_views": len(manifest["views"]),
        "dax_measures": manifest["dax_measure_count"],
        "documentation_files": len(required_docs),
        "openapi_paths": len(app.openapi()["paths"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-pipeline", action="store_true")
    args = parser.parse_args()
    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(), "pipeline": [],
    }
    try:
        if not args.skip_pipeline:
            for name, script, parameters in PIPELINE:
                report["pipeline"].append(_run(
                    name, [sys.executable, str(PROJECT_ROOT / "scripts" / script), *parameters]
                ))
        report["database"] = _database_checks()
        report["artifacts"] = _artifact_checks()
        report["static_checks"] = [
            _run("ruff", [sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"]),
            _run("mypy", [sys.executable, "-m", "mypy", "src", "scripts"]),
            _run("pytest", [
                sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                "--basetemp", ".pytest-tmp-project-verification",
            ]),
        ]
        report["status"] = "PASSED"
        report["completed_at"] = datetime.now(UTC).isoformat()
        output = PROJECT_ROOT / "reports" / "project_verification"
        output.mkdir(parents=True, exist_ok=True)
        (output / "verification.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print("PROJECT VERIFICATION PASSED")
        return 0
    except Exception as exc:
        report["status"] = "FAILED"
        report["error"] = str(exc)
        report["completed_at"] = datetime.now(UTC).isoformat()
        output = PROJECT_ROOT / "reports" / "project_verification"
        output.mkdir(parents=True, exist_ok=True)
        (output / "verification.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(f"PROJECT VERIFICATION FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
