from pathlib import Path

from src.decision_support import FacilityDecisionSupport, ScenarioEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"
WEIGHTS = PROJECT_ROOT / "analytics" / "decision_support_weights.yaml"


def test_efficiency_priority_is_ranked_with_fixed_weights() -> None:
    result = FacilityDecisionSupport(DATABASE, WEIGHTS).rank_efficiency_upgrades()
    assert len(result.ranking) == 6
    assert list(result.ranking["priority_rank"]) == [1, 2, 3, 4, 5, 6]
    assert result.ranking["priority_score"].between(0, 100).all()
    assert result.priority_facility == result.ranking.iloc[0]["facility_name"]
    assert result.decision_confidence in {"Low", "Moderate", "High"}
    assert "not an automatic investment decision" in result.answer
    assert result.evidence[0]["source"] == "analytics/decision_support_weights.yaml"


def test_historical_scenario_separates_fact_assumption_and_result() -> None:
    result = ScenarioEngine(DATABASE).run(
        "average_pue", -10, facilities=["Frankfurt Central"], baseline_year=2025
    )
    assert result.assumption["baseline_type"] == "historical_fact"
    assert result.assumption["user_supplied"] is True
    assert set(result.frame["baseline_type"]) == {"historical_fact"}
    assert (result.frame["scenario_value"] <= result.frame["baseline_value"]).all()
    assert "not a forecast or observed outcome" in result.answer


def test_demand_increase_is_bounded_for_percent_metrics() -> None:
    result = ScenarioEngine(DATABASE).run(
        "cpu_utilization_pct", 20, baseline_year=2025
    )
    assert result.frame["scenario_value"].between(0, 100).all()
    assert (result.frame["assumption_change_pct"] == 20).all()


def test_future_scenario_uses_forecast_baseline() -> None:
    result = ScenarioEngine(DATABASE).run(
        "cooling_cost", -15, facilities=["Dublin West"], baseline_year=2030
    )
    assert result.assumption["baseline_type"] == "forecast"
    assert set(result.frame["baseline_type"]) == {"forecast"}
    assert result.evidence[0]["method"] == "annual_linear_trend"


def test_unsafe_scenario_scale_is_rejected() -> None:
    try:
        ScenarioEngine(DATABASE).run("average_pue", 1000)
    except ValueError:
        pass
    else:
        raise AssertionError("An unbounded scenario should be rejected")


def test_every_forecast_metric_has_a_historical_scenario_path() -> None:
    engine = ScenarioEngine(DATABASE)
    assert len(engine.METRIC_MAP) == 16
    for metric_key in engine.METRIC_MAP:
        result = engine.run(metric_key, 5, baseline_year=2025)
        assert not result.frame.empty, metric_key
        assert result.assumption["preferred_direction"] in {"lower", "higher", "context"}
