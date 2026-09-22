from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .metrics_catalog import METRIC_BY_CODE


ISSUE_COLUMNS = [
    "severity",
    "check_name",
    "metric_code",
    "fiscal_year",
    "fiscal_period",
    "period_end",
    "issue_details",
    "detected_at_utc",
]


@dataclass
class DataQualityIssue:
    severity: str
    check_name: str
    metric_code: str | None
    fiscal_year: int | None
    fiscal_period: str | None
    period_end: str | None
    issue_details: str
    detected_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _issue(
    severity: str,
    check_name: str,
    details: str,
    metric_code: str | None = None,
    fiscal_year: int | None = None,
    fiscal_period: str | None = None,
    period_end: Any = None,
) -> DataQualityIssue:
    return DataQualityIssue(
        severity=severity,
        check_name=check_name,
        metric_code=metric_code,
        fiscal_year=int(fiscal_year) if fiscal_year is not None else None,
        fiscal_period=fiscal_period,
        period_end=str(period_end) if period_end is not None else None,
        issue_details=details,
        detected_at_utc=(
            datetime.now(timezone.utc)
            .replace(tzinfo=None)
            .isoformat(timespec="seconds")
        ),
    )


def validate_financial_facts(df: pd.DataFrame) -> pd.DataFrame:
    issues: list[DataQualityIssue] = []
    if df.empty:
        issues.append(_issue("ERROR", "EMPTY_DATASET", "No curated financial facts were produced."))
        return pd.DataFrame([item.to_dict() for item in issues], columns=ISSUE_COLUMNS)

    key_columns = [
        "company_cik",
        "metric_code",
        "period_end",
        "period_type",
        "fiscal_period",
        "unit",
    ]
    duplicate_mask = df.duplicated(key_columns, keep=False)
    for _, row in df[duplicate_mask].head(100).iterrows():
        issues.append(
            _issue(
                "ERROR",
                "DUPLICATE_BUSINESS_KEY",
                "More than one record exists at the curated reporting grain.",
                row["metric_code"],
                row["fiscal_year"],
                row["fiscal_period"],
                row["period_end"],
            )
        )

    if df["value"].isna().any():
        issues.append(_issue("ERROR", "NULL_VALUE", "One or more financial values are null."))

    for metric_code, metric in METRIC_BY_CODE.items():
        if not metric.non_negative:
            continue
        invalid = df[(df["metric_code"] == metric_code) & (df["value"] < 0)]
        for _, row in invalid.head(20).iterrows():
            issues.append(
                _issue(
                    "WARNING",
                    "UNEXPECTED_NEGATIVE_VALUE",
                    f"{metric.name} is negative; verify sign convention and source filing.",
                    metric_code,
                    row["fiscal_year"],
                    row["fiscal_period"],
                    row["period_end"],
                )
            )

    annual = df[df["period_type"] == "Annual"]
    if not annual.empty:
        latest_year = int(annual["fiscal_year"].max())
        required = {"REVENUE", "NET_INCOME", "TOTAL_ASSETS", "OPERATING_CASH_FLOW"}
        present = set(annual[annual["fiscal_year"] == latest_year]["metric_code"])
        for missing in sorted(required - present):
            issues.append(
                _issue(
                    "ERROR",
                    "MISSING_CRITICAL_METRIC",
                    f"Critical annual metric is missing for FY{latest_year}.",
                    missing,
                    latest_year,
                    "FY",
                )
            )

        annual_years = sorted(set(int(value) for value in annual["fiscal_year"].dropna()))
        for earlier, later in zip(annual_years, annual_years[1:]):
            if later - earlier > 1:
                issues.append(
                    _issue(
                        "WARNING",
                        "ANNUAL_PERIOD_GAP",
                        f"Annual history jumps from FY{earlier} to FY{later}.",
                        fiscal_year=later,
                        fiscal_period="FY",
                    )
                )

    flow_codes = {
        code for code, metric in METRIC_BY_CODE.items() if not metric.instant
    }
    quarterly_flows = df[
        (df["metric_code"].isin(flow_codes))
        & (df["period_type"] == "Quarterly")
        & (df["fiscal_period"].isin(["Q1", "Q2", "Q3", "Q4"]))
    ]
    quarter_number = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
    for (metric_code, fiscal_year), group in quarterly_flows.groupby(
        ["metric_code", "fiscal_year"]
    ):
        present = {quarter_number[value] for value in group["fiscal_period"]}
        for number in sorted(present):
            missing_prior = set(range(1, number)) - present
            if missing_prior:
                issues.append(
                    _issue(
                        "WARNING",
                        "QUARTER_SEQUENCE_GAP",
                        "A later standalone quarter exists while an earlier quarter is missing.",
                        metric_code,
                        fiscal_year,
                        f"Q{number}",
                    )
                )
                break

    # Accounting equation check: Assets approximately equal Liabilities + Equity.
    balance = df[df["metric_code"].isin(["TOTAL_ASSETS", "TOTAL_LIABILITIES", "EQUITY"])]
    if not balance.empty:
        pivot = balance.pivot_table(
            index=["period_end", "fiscal_year", "fiscal_period"],
            columns="metric_code",
            values="value",
            aggfunc="first",
        ).reset_index()
        required_cols = {"TOTAL_ASSETS", "TOTAL_LIABILITIES", "EQUITY"}
        if required_cols.issubset(pivot.columns):
            complete = pivot.dropna(subset=list(required_cols)).copy()
            complete["difference"] = (
                complete["TOTAL_ASSETS"]
                - complete["TOTAL_LIABILITIES"]
                - complete["EQUITY"]
            ).abs()
            complete["tolerance"] = complete["TOTAL_ASSETS"].abs() * 0.005
            for _, row in complete[complete["difference"] > complete["tolerance"]].iterrows():
                issues.append(
                    _issue(
                        "WARNING",
                        "ACCOUNTING_EQUATION_MISMATCH",
                        f"Assets differ from liabilities plus equity by {row['difference']:,.0f}.",
                        fiscal_year=row["fiscal_year"],
                        fiscal_period=row["fiscal_period"],
                        period_end=row["period_end"],
                    )
                )

    return pd.DataFrame([item.to_dict() for item in issues], columns=ISSUE_COLUMNS)


def quality_summary(issues: pd.DataFrame) -> dict[str, int]:
    if issues.empty:
        return {"errors": 0, "warnings": 0, "total": 0}
    severity = issues["severity"].value_counts().to_dict()
    return {
        "errors": int(severity.get("ERROR", 0)),
        "warnings": int(severity.get("WARNING", 0)),
        "total": int(len(issues)),
    }
