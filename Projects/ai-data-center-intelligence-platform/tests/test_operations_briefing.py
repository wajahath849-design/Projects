from pathlib import Path

from src.operations_briefing import OperationsBriefingEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE = PROJECT_ROOT / "database" / "datacenter.db"


def test_monthly_briefing_is_database_calculated_and_complete() -> None:
    briefing = OperationsBriefingEngine(DATABASE, PROJECT_ROOT).generate("2025-12")
    assert briefing.title == "Monthly Operations Brief — December 2025"
    assert set(briefing.sections) == {
        "ENERGY", "RELIABILITY", "NETWORK", "CAPACITY", "ANOMALIES", "FORECAST"
    }
    assert len(briefing.recommendations) == 3
    assert "RECOMMENDED INVESTIGATIONS" in briefing.answer
    assert briefing.evidence["month"] == "2025-12"
    assert briefing.evidence["forecast_method"] == "annual_linear_trend"


def test_invalid_briefing_month_is_rejected() -> None:
    try:
        OperationsBriefingEngine(DATABASE, PROJECT_ROOT).generate("December")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid month should be rejected")
