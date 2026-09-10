from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.forecasting import METRICS, contextualize_question, detect_metric
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator
from src.visualizer import build_plotly_chart


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * percentage
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "max_ms": round(max(values), 3) if values else 0.0,
        "mean_ms": round(sum(values) / len(values), 3) if values else 0.0,
    }


def update_context(state: dict, interpreted_question: str, pipeline: AnalyticsPipeline) -> None:
    selected_metric = detect_metric(interpreted_question)
    if selected_metric is not None:
        state["metric_key"] = selected_metric.key
    analysis = pipeline.analyzer.analyze(interpreted_question)
    if analysis.years:
        state["year"] = max(analysis.years)
    if analysis.facilities:
        state["facilities"] = analysis.facilities


def run_benchmark(
    questions: list[dict], output_path: Path, offline: bool, label: str
) -> dict:
    pipeline_started = time.perf_counter()
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()) if offline else AnalyticsPipeline()
    observed_initialization_ms = (time.perf_counter() - pipeline_started) * 1000
    contexts: dict[str, dict] = defaultdict(
        lambda: {"metric_key": None, "year": None, "facilities": []}
    )
    records = []

    print(
        f"Pipeline initialized in {observed_initialization_ms:.1f} ms "
        f"(instrumented {pipeline.initialization_ms:.1f} ms).",
        flush=True,
    )
    for index, item in enumerate(questions, start=1):
        question = item["question"]
        conversation = item.get("conversation") or item["id"]
        if item.get("reset_context"):
            contexts[conversation] = {"metric_key": None, "year": None, "facilities": []}
        state = contexts[conversation]
        previous_metric = next(
            (metric for metric in METRICS if metric.key == state["metric_key"]), None
        )

        request_started = time.perf_counter()
        memory_started = time.perf_counter()
        interpreted = contextualize_question(
            question,
            previous_metric,
            state["year"],
            state["facilities"],
            pipeline.forecaster.latest_complete_year(),
        )
        memory_ms = (time.perf_counter() - memory_started) * 1000

        error = None
        try:
            result = pipeline.ask(
                interpreted,
                upstream_timings={"memory_resolution_ms": memory_ms},
            )
            chart_started = time.perf_counter()
            if result.frame is not None:
                build_plotly_chart(result.frame, result.chart)
            chart_ms = (time.perf_counter() - chart_started) * 1000
            result.timings["chart_generation_ms"] += chart_ms
            update_context(state, interpreted, pipeline)
            status = result.status
            execution_path = result.execution_path
            cache_status = result.cache_status
            row_count = result.row_count
            llm_calls = result.llm_calls
            timings = result.timings
            answer_preview = result.answer[:300]
            sql = result.sql
            validation_status = result.validation_status
            source_tables = result.source_tables or []
            database_execution_reported_ms = result.execution_ms
        except Exception as exception:
            error = f"{type(exception).__name__}: {exception}"
            status = "benchmark_error"
            execution_path = "error"
            cache_status = "not_implemented"
            row_count = 0
            llm_calls = 0
            timings = {
                "routing_ms": 0.0,
                "memory_resolution_ms": round(memory_ms, 3),
                "rag_retrieval_ms": 0.0,
                "llm_sql_generation_ms": 0.0,
                "sql_validation_ms": 0.0,
                "database_execution_ms": 0.0,
                "answer_generation_ms": 0.0,
                "chart_generation_ms": 0.0,
                "forecast_ms": 0.0,
            }
            answer_preview = ""
            sql = None
            validation_status = None
            source_tables = []
            database_execution_reported_ms = None

        total_ms = (time.perf_counter() - request_started) * 1000
        llm_latency_ms = timings["llm_sql_generation_ms"] + timings["answer_generation_ms"]
        record = {
            "id": item["id"],
            "category": item["category"],
            "question": question,
            "interpreted_question": interpreted,
            "status": status,
            "execution_path": execution_path,
            "cache_status": cache_status,
            "row_count": row_count,
            "llm_calls": llm_calls,
            "timings": timings,
            "llm_latency_ms": round(llm_latency_ms, 3),
            "total_ms": round(total_ms, 3),
            "answer_preview": answer_preview,
            "sql": sql,
            "validation_status": validation_status,
            "source_tables": source_tables,
            "database_execution_reported_ms": database_execution_reported_ms,
            "error": error,
        }
        records.append(record)
        print(
            f"[{index:02d}/{len(questions):02d}] {item['id']} {execution_path}: "
            f"{total_ms:,.1f} ms, LLM calls={llm_calls}, status={status}",
            flush=True,
        )

    valid_records = [record for record in records if record["status"] != "benchmark_error"]
    total_values = [record["total_ms"] for record in valid_records]
    llm_values = [record["llm_latency_ms"] for record in valid_records]
    database_values = [record["timings"]["database_execution_ms"] for record in valid_records]
    path_counts = Counter(record["execution_path"] for record in valid_records)
    category_values: dict[str, list[float]] = defaultdict(list)
    path_values: dict[str, list[float]] = defaultdict(list)
    for record in valid_records:
        category_values[record["category"]].append(record["total_ms"])
        path_values[record["execution_path"]].append(record["total_ms"])

    stage_summary = {
        stage: distribution([record["timings"][stage] for record in valid_records])
        for stage in next(iter(valid_records), {"timings": {}})["timings"]
    }
    total_count = len(valid_records)
    summary = {
        "total_latency": distribution(total_values),
        "database_latency": distribution(database_values),
        "llm_latency": distribution(llm_values),
        "stages": stage_summary,
        "categories": {
            category: distribution(values) for category, values in sorted(category_values.items())
        },
        "execution_paths": {
            path: distribution(values) for path, values in sorted(path_values.items())
        },
        "execution_path_counts": dict(path_counts),
        "execution_path_rates": {
            path: round(count / total_count, 4) if total_count else 0.0
            for path, count in path_counts.items()
        },
        "cache_hit_rate": round(
            sum(record["cache_status"] == "hit" for record in valid_records) / total_count, 4
        ) if total_count else 0.0,
        "total_llm_calls": sum(record["llm_calls"] for record in valid_records),
        "pipeline_error_count": sum(
            record["status"].endswith("_error") for record in valid_records
        ),
        "benchmark_harness_errors": len(records) - len(valid_records),
    }
    report = {
        "benchmark": label,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "question_count": len(records),
        "mode": "offline" if offline else "live_ollama",
        "ollama_model": None if offline else settings.ollama_model,
        "database_path": str(settings.database_path),
        "pipeline_initialization_ms": round(observed_initialization_ms, 3),
        "summary": summary,
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Saved benchmark report to {output_path}", flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the instrumented analytics pipeline.")
    parser.add_argument(
        "--questions",
        type=Path,
        default=PROJECT_ROOT / "evaluation/performance_questions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation/results/performance_baseline.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--label", default="phase_1_before_optimization")
    args = parser.parse_args()
    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    if args.limit is not None:
        questions = questions[: max(0, args.limit)]
    run_benchmark(questions, args.output, args.offline, args.label)


if __name__ == "__main__":
    main()
