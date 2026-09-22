import json
from pathlib import Path

from apple_financial_etl.transformer import transform_company_facts


FIXTURE = Path(__file__).parent / "fixtures" / "companyfacts_minimal.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_selects_quarter_duration_instead_of_ytd():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    q2 = df[
        (df["metric_code"] == "REVENUE")
        & (df["fiscal_year"] == 2024)
        & (df["fiscal_period"] == "Q2")
    ]
    assert len(q2) == 1
    assert q2.iloc[0]["value"] == 90753


def test_latest_filing_wins_for_same_reporting_period():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    annual = df[
        (df["metric_code"] == "REVENUE")
        & (df["fiscal_year"] == 2024)
        & (df["fiscal_period"] == "FY")
    ]
    assert len(annual) == 1
    assert annual.iloc[0]["value"] == 391100
    assert annual.iloc[0]["filed_date"].isoformat() == "2025-10-31"


def test_derives_fourth_quarter_from_annual_less_q1_q2_q3():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    q4 = df[
        (df["metric_code"] == "REVENUE")
        & (df["fiscal_year"] == 2024)
        & (df["fiscal_period"] == "Q4")
    ]
    assert len(q4) == 1
    assert q4.iloc[0]["value"] == 94995
    assert bool(q4.iloc[0]["is_derived"]) is True


def test_reclassifies_year_end_balance_as_q4_snapshot():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    q4_assets = df[
        (df["metric_code"] == "TOTAL_ASSETS")
        & (df["fiscal_year"] == 2024)
        & (df["fiscal_period"] == "Q4")
        & (df["period_type"] == "Quarterly")
    ]
    assert len(q4_assets) == 1
    assert q4_assets.iloc[0]["value"] == 364980
    assert q4_assets.iloc[0]["derivation_method"] == (
        "Q4 ending balance = fiscal year-end balance"
    )


def test_converts_ytd_cash_flow_to_standalone_quarters():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    ocf = df[(df["metric_code"] == "OPERATING_CASH_FLOW") & (df["fiscal_year"] == 2024)]
    values = dict(zip(ocf["fiscal_period"], ocf["value"]))
    assert values["Q1"] == 30000
    assert values["Q2"] == 25000
    assert values["Q3"] == 30000
    assert values["Q4"] == 33254
    q2 = ocf[ocf["fiscal_period"] == "Q2"].iloc[0]
    assert bool(q2["is_derived"]) is True
    assert "fiscal YTD" in q2["derivation_method"]


def test_derived_q4_has_quarter_date_range():
    df = transform_company_facts(load_fixture(), history_years=5, as_of_year=2025)
    q4 = df[
        (df["metric_code"] == "REVENUE")
        & (df["fiscal_year"] == 2024)
        & (df["fiscal_period"] == "Q4")
    ].iloc[0]
    assert q4["period_start"].isoformat() == "2024-06-30"
    assert q4["period_end"].isoformat() == "2024-09-28"
    assert q4["duration_days"] == 91
