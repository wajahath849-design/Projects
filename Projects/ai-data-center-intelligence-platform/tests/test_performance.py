import time

from src.performance import PerformanceTrace, TIMING_STAGES
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator


def test_performance_trace_reports_every_required_stage():
    trace = PerformanceTrace({"memory_resolution_ms": 1.25})
    with trace.stage("routing_ms"):
        time.sleep(0.001)
    snapshot = trace.snapshot()
    assert tuple(snapshot) == TIMING_STAGES
    assert snapshot["memory_resolution_ms"] == 1.25
    assert snapshot["routing_ms"] >= 1.0


def test_pipeline_results_include_observability_fields():
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    result = pipeline.ask(
        "Which facility had the highest average PUE in 2020?",
        upstream_timings={"memory_resolution_ms": 0.5},
    )
    assert result.status == "ok"
    assert result.execution_path == "fast_ranking"
    assert result.cache_status == "not_implemented"
    assert result.row_count == 1
    assert result.llm_calls == 0
    assert set(result.timings) == set(TIMING_STAGES)
    assert result.timings["memory_resolution_ms"] == 0.5
    assert result.timings["rag_retrieval_ms"] >= 0
    assert result.timings["sql_validation_ms"] >= 0
    assert result.timings["database_execution_ms"] >= 0
    assert result.total_ms >= sum(result.timings.values()) * 0.95


def test_router_only_request_is_timed_and_logged_as_router_path():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Drop the facilities table"
    )
    assert result.status == "blocked"
    assert result.execution_path == "router_only"
    assert result.timings["routing_ms"] > 0
    assert sum(value for key, value in result.timings.items() if key != "routing_ms") == 0


def test_forecast_request_separates_forecast_time():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Forecast Frankfurt PUE through 2030"
    )
    assert result.status == "forecast"
    assert result.execution_path == "forecast"
    assert result.timings["forecast_ms"] > 0
    assert result.timings["llm_sql_generation_ms"] == 0
    assert result.llm_calls == 0
