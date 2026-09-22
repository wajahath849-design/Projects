import json
from pathlib import Path

from apple_financial_etl.transformer import transform_company_facts
from apple_financial_etl.validation import quality_summary, validate_financial_facts


FIXTURE = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"


def test_fixture_has_no_quality_errors():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    facts = transform_company_facts(payload, history_years=5, as_of_year=2025)
    issues = validate_financial_facts(facts)
    summary = quality_summary(issues)
    assert summary["errors"] == 0
