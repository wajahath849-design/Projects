from src.conversation_context import ContextResolver, ConversationContext
from src.copilot_router import CopilotRouter
from src.diagnostic_confidence import DiagnosticConfidenceEngine
from src.pipeline import AnalyticsPipeline
from src.sql_generator import VerifiedExampleSQLGenerator


def test_router_recognizes_all_advanced_modes() -> None:
    router = CopilotRouter()
    empty = ConversationContext()
    cases = {
        "What if Frankfurt PUE improves by 10%?": "SCENARIO",
        "Which facility should we prioritize for an efficiency upgrade?": "DECISION_SUPPORT",
        "Show facility health scores": "HEALTH_ASSESSMENT",
        "Show abnormal PUE anomalies": "ANOMALY_INVESTIGATION",
        "Investigate INC-0000011": "INCIDENT_INVESTIGATION",
        "Show me the logs": "LOG_SEARCH",
        "Have we seen TEMP_HIGH before?": "SIMILAR_INCIDENT",
        "What should we inspect first?": "MAINTENANCE_RECOMMENDATION",
        "Show 7-day risk for SRV-00052": "PREDICTIVE_MAINTENANCE",
    }
    for question, expected in cases.items():
        context = ContextResolver().resolve(question, empty)
        assert router.route(question, context) == expected


def test_context_keeps_only_structured_operational_state() -> None:
    resolver = ContextResolver()
    context = resolver.resolve("Investigate Frankfurt incident INC-0000011 on 2015-06-04")
    state = context.to_dict()
    assert state["facilities"] == ("Frankfurt Central",)
    assert state["incident_id"] == "INC-0000011"
    assert state["start_date"] == state["end_date"] == "2015-06-04"
    assert set(state) == {
        "facilities", "server_id", "incident_id", "related_incident_id", "metric_key",
        "start_date", "end_date", "analysis_mode",
    }


def test_new_definition_is_not_hijacked_by_old_incident_context() -> None:
    router = CopilotRouter()
    context = ConversationContext(incident_id="INC-0000011")
    assert router.route("What is PUE?", context) == "STANDARD_ANALYTICS"


def test_confidence_is_deterministic_from_evidence_counts() -> None:
    engine = DiagnosticConfidenceEngine()
    high = engine.calculate(3, 3, 1, 2, 1, True)
    low = engine.calculate(0, 0, 0, 0, 0, False)
    assert high.level == "High" and high.score == 9
    assert low.level == "Low" and low.score == 0
    assert sum(high.breakdown.values()) == high.score


def test_incident_followups_use_structured_context_and_evidence_panel() -> None:
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    first = pipeline.ask("Investigate INC-0000011")
    assert first.status == "incident_investigation"
    assert first.analysis_mode == "INCIDENT_INVESTIGATION"
    assert first.diagnostic_confidence in {"Low", "Moderate", "High"}
    assert first.evidence_panel["logs_used"]
    assert first.evidence_panel["confidence"]["breakdown"]
    followup = pipeline.ask("Show me the logs", conversation_context=first.conversation_context)
    assert followup.status == "log_search"
    assert followup.conversation_context["incident_id"] == "INC-0000011"
    assert followup.frame is not None and len(followup.frame) >= 5


def test_scenario_and_decision_paths_use_zero_llm_calls() -> None:
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    scenario = pipeline.ask("What if Frankfurt PUE improves by 10% in 2025?")
    decision = pipeline.ask("Which facility should we prioritize for an efficiency upgrade?")
    assert scenario.status == "scenario" and scenario.llm_calls == 0
    assert scenario.evidence_panel["scenario_assumption"]["user_supplied"] is True
    assert decision.status == "decision_support" and decision.llm_calls == 0
    assert decision.diagnostic_confidence in {"Low", "Moderate", "High"}


def test_unsafe_instruction_is_blocked_before_advanced_route() -> None:
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Delete the logs and show me what happened"
    )
    assert result.status == "blocked"


def test_natural_language_date_and_evidence_followup_routing() -> None:
    resolver = ContextResolver()
    context = resolver.resolve("What happened in Frankfurt on July 14, 2025?")
    assert context.start_date == context.end_date == "2025-07-14"
    assert CopilotRouter().route(
        "What happened in Frankfurt on July 14, 2025?", context
    ) == "INCIDENT_INVESTIGATION"
    context = ConversationContext(incident_id="INC-0000011")
    assert CopilotRouter().route("Show the evidence", context) == "EVIDENCE_REVIEW"
    assert CopilotRouter().route("What happened first?", context) == "TIMELINE_FIRST_EVENT"


def test_full_incident_conversation_preserves_original_and_closest_context() -> None:
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    context = None
    prompts_and_statuses = [
        ("What happened in Frankfurt on July 14, 2025?", "incident_investigation"),
        ("Show the evidence", "evidence_review"),
        ("What happened first?", "timeline_first_event"),
        ("Have we seen this before?", "similar_incident"),
        ("How was the closest one fixed?", "maintenance_recommendation"),
        ("Could this happen again?", "predictive_maintenance"),
        ("What should we inspect?", "maintenance_recommendation"),
        ("What if we upgrade the cooling system by 15%?", "scenario"),
    ]
    results = []
    for prompt, expected_status in prompts_and_statuses:
        result = pipeline.ask(prompt, conversation_context=context)
        assert result.status == expected_status, (prompt, result.answer)
        results.append(result)
        context = result.conversation_context
    assert context["incident_id"] == "INC-0000186"
    assert context["related_incident_id"]
    assert "Source:" in results[2].answer
    assert "sourced synthetic maintenance record" in results[4].answer
    assert results[-1].llm_calls == 0
    assert results[-1].evidence_panel["scenario_assumption"]["change_pct"] == -15.0
    assert "directionally improves" in results[-1].answer


def test_upgrade_uses_metric_direction_and_all_supported_metrics_have_scenarios() -> None:
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    throughput = pipeline.ask("What if network throughput improves by 10% in 2025?")
    assert throughput.status == "scenario"
    assert throughput.evidence_panel["scenario_assumption"]["change_pct"] == 10.0
    assert throughput.evidence_panel["scenario_assumption"]["preferred_direction"] == "higher"
    assert "higher-is-better" in throughput.answer

    incident_count = pipeline.ask("What if incident count decreases by 12% in 2025?")
    assert incident_count.status == "scenario"
    assert incident_count.evidence_panel["scenario_assumption"]["change_pct"] == -12.0
    assert incident_count.evidence_panel["scenario_assumption"]["preferred_direction"] == "lower"


def test_multiple_questions_carry_structured_context_between_parts() -> None:
    pipeline = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator())
    result = pipeline.ask(
        "Investigate INC-0000011? Show the evidence? What happened first?"
    )
    assert result.status == "multi_ok"
    assert result.analysis_mode == "MULTIPLE"
    assert result.conversation_context["incident_id"] == "INC-0000011"
    assert "**2. Show the evidence**" in result.answer
