from src.pipeline import AnalyticsPipeline


class ExplodingGenerator:
    def generate(self, question, context):
        raise AssertionError("Fast routes must not invoke the SQL model")


def pipeline():
    return AnalyticsPipeline(generator=ExplodingGenerator())


def test_definition_uses_glossary_without_llm_or_sql():
    result = pipeline().ask("What is PUE?")
    assert result.status == "knowledge"
    assert result.execution_path == "fast_definition"
    assert result.llm_calls == 0
    assert result.sql is None
    assert "Power Usage Effectiveness" in result.answer


def test_simple_kpi_uses_parameterized_aggregate_template():
    result = pipeline().ask("What was Frankfurt average PUE in 2024?")
    assert result.status == "ok"
    assert result.execution_path == "fast_kpi"
    assert result.llm_calls == 0
    assert result.parameters == [2024, "Frankfurt Central"]
    assert "?" in result.sql
    assert result.frame.iloc[0]["facility_name"] == "Frankfurt Central"


def test_ranking_uses_fast_path_and_returns_correct_leader():
    result = pipeline().ask("Which facility had the highest average PUE in 2020?")
    assert result.execution_path == "fast_ranking"
    assert result.llm_calls == 0
    assert result.frame.iloc[0]["facility_name"] == "Singapore South"


def test_comparison_and_trend_use_fast_paths():
    comparison = pipeline().ask("Compare Dublin and Frankfurt PUE in 2023")
    assert comparison.execution_path == "fast_comparison"
    assert set(comparison.frame["facility_name"]) == {"Dublin West", "Frankfurt Central"}
    trend = pipeline().ask("Show annual cooling cost from 2015 to 2025")
    assert trend.execution_path == "fast_trend"
    assert len(trend.frame) == 11
    assert trend.llm_calls == 0
    facility_trend = pipeline().ask("Average CPU utilization by facility by year")
    assert facility_trend.execution_path == "fast_trend"
    assert len(facility_trend.frame) == 66


def test_incident_count_uses_sum_semantics():
    result = pipeline().ask("How many incidents occurred in 2020?")
    assert result.execution_path == "fast_kpi"
    assert int(result.frame.iloc[0]["metric_value"]) > 0


def test_unsupported_detail_grains_remain_on_ai_path():
    router = pipeline().fast_router
    analyzer = pipeline().analyzer
    for question in [
        "Average CPU utilization by server type",
        "Count incidents by facility and root cause",
        "Show monthly PUE during 2025",
        "What was SRV-00001 CPU utilization in 2024?",
    ]:
        decision = router.route(question, analyzer.analyze(question), 2025)
        assert decision.category == "AI"


def test_direction_question_remains_on_existing_forecast_direction_path():
    result = pipeline().ask("Will cooling cost increase or decrease?")
    assert result.status == "forecast_direction"
    assert result.execution_path == "forecast"
