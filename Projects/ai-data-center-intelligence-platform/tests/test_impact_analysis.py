from pathlib import Path

from src.impact.engine import ImpactAnalysisEngine
from src.sustainability.engine import CostCarbonEngine


ROOT = Path(__file__).resolve().parents[1]


def sustainability() -> CostCarbonEngine:
    return CostCarbonEngine(
        ROOT / "database/datacenter.db",
        ROOT / "data/assumptions/energy_prices.csv",
        ROOT / "data/assumptions/carbon_intensity.csv",
        ROOT / "analytics/efficiency_opportunity_weights.yaml",
    )


def engine() -> ImpactAnalysisEngine:
    return ImpactAnalysisEngine(ROOT / "database/datacenter.db", sustainability())


def test_correlation_reports_sample_scope_interval_and_noncausal_language() -> None:
    result = engine().correlation("pue", "cooling_power_kw", facility_id="DC-FRA-01", start_date="2024-01-01", end_date="2025-12-31")
    assert result.sample_size > 100
    assert result.confidence_interval_95 is not None
    assert result.scope == "DC-FRA-01"
    assert "does not establish causation" in result.interpretation
    assert {"pue", "cooling_power_kw"} <= set(result.chart_data)


def test_lead_lag_has_declared_temporal_direction_and_sample_sizes() -> None:
    result = engine().lead_lag("pue", "latency_ms", facility_id="DC-FRA-01", max_lag_days=3)
    assert result["lag_days"].tolist() == [-3, -2, -1, 0, 1, 2, 3]
    assert (result["sample_size"] > 100).all()
    assert result["interpretation"].str.contains("not causation").all()


def test_incident_impact_has_before_during_after_and_cost_fields() -> None:
    result = engine().incident_impact("INC-0000001")
    assert result["claim_level"] == "descriptive_before_during_after"
    assert result["duration_minutes"] == 8
    assert result["affected_servers_same_facility_day"] >= 1
    assert result["metrics"]
    assert "causal" in result["caveat"]
    assert "estimated_excess_energy_kwh" in result["modeled_cost_energy_carbon_impact"]


def test_intervention_falls_back_when_design_assumptions_fail() -> None:
    result = engine().intervention(
        "pue", "2025-01-01", treated_facility_id="DC-FRA-01",
        comparison_facility_id="DC-PDX-01", window_days=45,
    )
    assert result.method in {"difference_in_differences", "descriptive_before_after"}
    assert result.evidence_score["not_a_probability"] is True
    assert "not described as causal" in result.interpretation
    assert result.sample_size > 0
