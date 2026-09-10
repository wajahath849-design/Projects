from src.conversation_context import ContextResolver
from src.copilot_router import CopilotRouter
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator


def pipeline() -> AnalyticsPipeline:
    return AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())


def test_router_recognizes_new_analytics_intents() -> None:
    router = CopilotRouter()
    cases = {
        "What will the energy cost be in 2030?": "COST_ANALYSIS",
        "Estimate carbon emissions in 2030": "CARBON_ANALYSIS",
        "Model 10% energy savings": "EFFICIENCY_SCENARIO",
        "Correlate PUE and cooling power": "CORRELATION_ANALYSIS",
        "What was the incident impact of INC-0000001?": "IMPACT_ANALYSIS",
        "Did the upgrade cause PUE to fall?": "CAUSAL_ANALYSIS",
        "Run a multi-agent investigation": "MULTI_AGENT_INVESTIGATION",
        "Show live anomalies": "REALTIME_ANOMALY",
    }
    for question, expected in cases.items():
        context = ContextResolver().resolve(question)
        assert router.route(question, context) == expected


def test_cost_and_carbon_future_questions_use_governed_engines() -> None:
    cost = pipeline().ask("What will the cooling cost and energy price be in 2030?")
    carbon = pipeline().ask("What will carbon emissions be in 2030?")
    assert cost.status == "cost_forecast" and cost.llm_calls == 0
    assert carbon.status == "carbon_forecast" and carbon.llm_calls == 0
    assert "synthetic" in cost.answer.lower()
    assert "not an audited" in carbon.answer.lower()
    assert cost.frame is not None and len(cost.frame) == 6


def test_chat_handles_flexible_wording_multiple_questions_and_followup_context() -> None:
    result = pipeline().ask(
        "Tell me the modeled energy cost for 2020 and 2025? Also estimate carbon in 2030?"
    )
    assert result.status == "multi_ok"
    assert "**1." in result.answer and "**2." in result.answer
    assert result.llm_calls == 0
    first = pipeline().ask("Show real-time status")
    if first.status != "clarification":
        follow = pipeline().ask("and the anomalies?", conversation_context=first.conversation_context)
        assert follow.conversation_context["data_mode"] == "live"


def test_missing_causal_inputs_produce_counter_question() -> None:
    result = pipeline().ask("Did the upgrade cause PUE to fall?")
    assert result.status == "clarification"
    assert "date" in result.answer.lower()


def test_correlation_and_incident_impact_are_grounded() -> None:
    correlation = pipeline().ask("Correlate PUE and cooling power in Frankfurt during 2025")
    impact = pipeline().ask("What was the incident impact of INC-0000001?")
    assert correlation.status == "correlation_analysis"
    assert "does not establish causation" in correlation.answer
    assert impact.status == "impact_analysis"
    assert impact.frame is not None and not impact.frame.empty
