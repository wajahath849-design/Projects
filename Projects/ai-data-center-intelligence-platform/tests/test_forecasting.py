import pandas as pd

from src.forecasting import (
    METRICS,
    MetricForecaster,
    asks_trend_direction,
    contextualize_question,
    detect_metric,
    detect_metrics,
    has_forecast_intent,
    resolve_target_year,
)
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator


def metric(key):
    return next(item for item in METRICS if item.key == key)


def test_metric_detection_covers_operational_domains():
    assert detect_metric("Forecast cooling cost in 2030").key == "cooling_cost"
    assert detect_metric("What will CPU utilization be in 2030?").key == "cpu_utilization_pct"
    assert detect_metric("Predict network latency in 2030").key == "latency_ms"
    assert detect_metric("How many incidents will there be in 2030?").key == "incident_count"
    assert detect_metric("Estimate the price of cooling in 2030").key == "cooling_cost"
    assert detect_metric("Estimate the price of power in 2030") is None
    assert detect_metric("compare the price between 2020 2015 and 2025").key == "cooling_cost"
    assert [item.key for item in detect_metrics("Forecast PUE, cooling cost, and latency in 2030")] == [
        "average_pue", "cooling_cost", "latency_ms"
    ]


def test_flexible_future_date_language():
    assert resolve_target_year("cooling 2030", 2025) == 2030
    assert resolve_target_year("predict cooling next year", 2025) == 2026
    assert resolve_target_year("cooling five years from now", 2025) == 2030
    assert resolve_target_year("cooling 5 years from now", 2025) == 2030
    assert has_forecast_intent("What will cooling be?")
    assert asks_trend_direction("Will the price increase or decrese?")


def test_conversational_follow_up_uses_previous_metric():
    assert contextualize_question("2040", metric("latency_ms")) == "Forecast Network Latency in 2040"
    contextualized = contextualize_question("will it increase or decrease?", metric("cooling_cost"))
    assert "Annual Cooling Cost" in contextualized

    facility_follow_up = contextualize_question(
        "what about Dublin?", metric("latency_ms"), 2030, ["Frankfurt Central"]
    )
    assert "Network Latency" in facility_follow_up
    assert "Dublin" in facility_follow_up
    assert "Frankfurt Central" not in facility_follow_up
    assert "2030" in facility_follow_up

    metric_follow_up = contextualize_question(
        "and PUE?", metric("latency_ms"), 2030, ["Frankfurt Central"]
    )
    assert "PUE" in metric_follow_up
    assert "Frankfurt Central" in metric_follow_up
    assert "2030" in metric_follow_up


def test_bare_future_year_asks_for_the_missing_metric():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask("2040")
    assert result.status == "clarification"
    assert "Which forecast metric" in result.answer


def test_generic_price_historical_comparison_uses_cooling_cost():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "compare the price between 2020 2015 and 2025"
    )
    assert result.status == "historical"
    assert set(result.frame["year"]) == {2015, 2020, 2025}
    assert set(result.frame["metric"]) == {"Annual Cooling Cost"}
    assert "increased" in result.answer or "decreased" in result.answer


def test_generic_price_direction_handles_misspelling():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "the price will increase or decrese?"
    )
    assert result.status == "forecast_direction"
    assert "Annual Cooling Cost" in result.answer
    assert "increasing" in result.answer or "decreasing" in result.answer


def test_definition_questions_use_grounded_project_knowledge():
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    for question in ["What is PUE?", "what is the powercooling?"]:
        result = pipeline.ask(question)
        assert result.status == "knowledge"
        assert result.validation_status == "rag_grounded"
        assert result.retrieved_context


def test_pue_forecast_uses_current_database_and_bounds():
    result = MetricForecaster("database/datacenter.db").forecast(metric("average_pue"), 2030)
    assert result.training_end_year == 2025
    assert len(result.frame) == 7
    assert result.frame["predicted_value"].between(1, 2).all()
    assert (result.frame["lower_95"] <= result.frame["predicted_value"]).all()
    assert (result.frame["predicted_value"] <= result.frame["upper_95"]).all()


def test_forecaster_refits_instead_of_caching(monkeypatch):
    forecaster = MetricForecaster("unused.db")
    first = pd.DataFrame({
        "facility_name": ["Test"] * 5,
        "year": [2021, 2022, 2023, 2024, 2025],
        "metric_value": [1.50, 1.48, 1.46, 1.44, 1.42],
    })
    second = pd.concat([
        first,
        pd.DataFrame({"facility_name": ["Test"], "year": [2026], "metric_value": [1.30]}),
    ])
    state = {"frame": first}
    monkeypatch.setattr(forecaster, "load_history", lambda selected: (state["frame"], "SELECT history"))
    before = forecaster.forecast(metric("average_pue"), 2030, ["Test"])
    state["frame"] = second
    after = forecaster.forecast(metric("average_pue"), 2030, ["Test"])
    assert before.training_end_year == 2025
    assert after.training_end_year == 2026
    assert before.frame.loc[0, "predicted_value"] != after.frame.loc[0, "predicted_value"]


def test_pipeline_routes_future_metrics_without_ollama():
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    for question in [
        "What will the PUE be in 2030?",
        "Forecast cooling cost in 2030",
        "What will Frankfurt network latency be in 2030?",
        "What will CPU utilization be in 2030?",
        "How much downtime will there be in 2030?",
    ]:
        result = pipeline.ask(question)
        assert result.status == "forecast"
        assert result.validation_status == "forecast_model"
        assert result.frame is not None and not result.frame.empty


def test_future_static_metric_requests_clarification():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "What will server count be in 2030?"
    )
    assert result.status == "clarification"
    assert "Supported time-series metrics" in result.answer

    unsupported_price = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "What will the price of power be in 2030?"
    )
    assert unsupported_price.status == "clarification"
    assert "only monetary time series" in unsupported_price.answer


def test_missing_forecast_date_asks_a_counter_question():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "What will cooling power be?"
    )
    assert result.status == "clarification"
    assert "Which future year" in result.answer
    assert "latest complete data year is 2025" in result.answer


def test_relative_future_date_is_resolved_automatically():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Predict cooling power next year"
    )
    assert result.status == "forecast"
    assert set(result.frame["forecast_year"]) == {2026}


def test_multiple_forecast_metrics_in_one_sentence():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Forecast PUE, cooling cost, and latency in 2030"
    )
    assert result.status == "forecast"
    assert result.chart is None
    assert {"PUE", "Annual Cooling Cost", "Network Latency"} <= set(result.frame["metric"])


def test_multiple_separated_questions_are_combined():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "What will PUE be in 2030? What will cooling cost be in 2030?"
    )
    assert result.status == "multi_ok"
    assert "**1." in result.answer and "**2." in result.answer
    assert set(result.frame["question_number"]) == {1, 2}


def test_multiple_questions_can_return_partial_clarification():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "What will PUE be in 2030? What will server count be in 2030?"
    )
    assert result.status == "multi_partial"
    assert "Supported time-series metrics" in result.answer


def test_weak_incident_trend_is_caveated():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "How many incidents will there be in 2030?"
    )
    assert result.status == "forecast"
    assert "low confidence" in result.answer


def test_every_registered_metric_can_be_forecast():
    forecaster = MetricForecaster("database/datacenter.db")
    for selected in METRICS:
        result = forecaster.forecast(selected, 2030)
        assert not result.frame.empty
        assert result.frame["predicted_value"].notna().all()
