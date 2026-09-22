from __future__ import annotations

import json
from pathlib import Path

from apple_financial_etl.transformer import transform_company_facts
from apple_financial_etl.validation import validate_financial_facts

root = Path(__file__).resolve().parents[1]
fixture = root / "tests/fixtures/companyfacts_minimal.json"
payload = json.loads(fixture.read_text(encoding="utf-8"))
facts = transform_company_facts(payload, history_years=10, as_of_year=2025)
issues = validate_financial_facts(facts)
output = root / "data/sample"
output.mkdir(parents=True, exist_ok=True)
facts.to_csv(output / "offline_sample_financial_facts.csv", index=False)
issues.to_csv(output / "offline_sample_quality_issues.csv", index=False)
print(f"Created {len(facts)} facts and {len(issues)} quality issues in {output}")
