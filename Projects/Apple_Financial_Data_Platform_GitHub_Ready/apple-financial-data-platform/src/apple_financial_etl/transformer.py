from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from .metrics_catalog import METRICS, MetricDefinition

LOGGER = logging.getLogger(__name__)

FACT_COLUMNS = [
    "company_cik",
    "metric_code",
    "metric_name",
    "statement_name",
    "category_name",
    "taxonomy",
    "source_tag",
    "unit",
    "value",
    "period_start",
    "period_end",
    "duration_days",
    "period_type",
    "fiscal_year",
    "fiscal_period",
    "form_type",
    "filed_date",
    "accession_number",
    "source_url",
    "is_derived",
    "derivation_method",
    "business_key",
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _fiscal_year(period_end: date, fiscal_period: str) -> int:
    # Apple's Q1 ends in December of the prior calendar year.
    if fiscal_period == "Q1" and period_end.month >= 10:
        return period_end.year + 1
    return period_end.year


def _source_url(accession_number: str, cik: str) -> str:
    accession_plain = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_plain}/"


def _business_key(row: dict[str, Any]) -> str:
    raw = "|".join(
        str(row.get(name, ""))
        for name in (
            "company_cik",
            "metric_code",
            "period_end",
            "period_type",
            "fiscal_period",
            "unit",
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _candidate_rows(
    payload: dict[str, Any], metric: MetricDefinition, tag: str, tag_priority: int
) -> Iterable[dict[str, Any]]:
    company_cik = str(payload.get("cik", "")).zfill(10)
    company_facts = payload.get("facts", {}).get("us-gaap", {})
    concept = company_facts.get(tag)
    if not concept:
        return []

    rows: list[dict[str, Any]] = []
    units = concept.get("units", {})
    for preferred_unit in metric.preferred_units:
        facts = units.get(preferred_unit, [])
        for fact in facts:
            form_type = fact.get("form")
            fiscal_period = fact.get("fp")
            if form_type not in {"10-K", "10-Q"}:
                continue
            if fiscal_period not in {"FY", "Q1", "Q2", "Q3", "Q4"}:
                continue
            if fact.get("val") is None or not fact.get("end") or not fact.get("filed"):
                continue

            period_end = _parse_date(fact.get("end"))
            period_start = _parse_date(fact.get("start"))
            if period_end is None:
                continue
            duration_days = (period_end - period_start).days + 1 if period_start else None

            if fiscal_period == "FY" and form_type == "10-K":
                period_type = "Annual"
                target_duration = 365
            elif fiscal_period in {"Q1", "Q2", "Q3", "Q4"} and form_type in {"10-Q", "10-K"}:
                period_type = "Quarterly"
                target_duration = 91
            else:
                continue

            # Duration metrics often include quarter-to-date and year-to-date values.
            # Keep both as candidates and let ranking choose the duration closest to the target.
            duration_distance = 0 if metric.instant else (
                abs((duration_days or target_duration) - target_duration)
            )

            row = {
                "company_cik": company_cik,
                "metric_code": metric.code,
                "metric_name": metric.name,
                "statement_name": metric.statement,
                "category_name": metric.category,
                "taxonomy": "us-gaap",
                "source_tag": tag,
                "unit": preferred_unit,
                "value": float(fact["val"]),
                "period_start": period_start,
                "period_end": period_end,
                "duration_days": duration_days,
                "period_type": period_type,
                "fiscal_year": _fiscal_year(period_end, fiscal_period),
                "fiscal_period": fiscal_period,
                "form_type": form_type,
                "filed_date": _parse_date(fact.get("filed")),
                "accession_number": fact.get("accn", ""),
                "source_url": _source_url(fact.get("accn", ""), company_cik)
                if fact.get("accn")
                else "",
                "is_derived": False,
                "derivation_method": None,
                "tag_priority": tag_priority,
                "duration_distance": duration_distance,
            }
            rows.append(row)
    return rows


def _deduplicate(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return candidates

    candidates = candidates.copy()
    candidates["filed_date"] = pd.to_datetime(candidates["filed_date"])
    candidates["period_end"] = pd.to_datetime(candidates["period_end"])
    candidates["period_start"] = pd.to_datetime(candidates["period_start"])

    # Ranking order:
    # 1) correct duration (quarter vs annual), 2) preferred XBRL tag,
    # 3) latest filing, allowing restatements to replace older values.
    candidates = candidates.sort_values(
        by=["duration_distance", "tag_priority", "filed_date", "accession_number"],
        ascending=[True, True, False, False],
    )
    business_grain = [
        "company_cik",
        "metric_code",
        "period_end",
        "period_type",
        "fiscal_period",
        "unit",
    ]
    result = candidates.drop_duplicates(subset=business_grain, keep="first").copy()
    return result.drop(columns=["tag_priority", "duration_distance"])


def _normalize_cumulative_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """Convert fiscal year-to-date Q2/Q3 facts into standalone quarter values."""
    if df.empty:
        return df

    result = df.copy()
    flow_codes = {metric.code for metric in METRICS if not metric.instant}
    quarter_order = {"Q1": 1, "Q2": 2, "Q3": 3}

    for (_, metric_code, fiscal_year, unit), group in result[
        (result["metric_code"].isin(flow_codes))
        & (result["period_type"] == "Quarterly")
        & (result["fiscal_period"].isin(quarter_order))
    ].groupby(["company_cik", "metric_code", "fiscal_year", "unit"]):
        ordered = group.assign(
            _quarter_number=group["fiscal_period"].map(quarter_order)
        ).sort_values("_quarter_number")
        prior_standalone_total = 0.0
        prior_period_end = None
        completed_quarters = 0
        rows_to_drop: list[int] = []

        for index, row in ordered.iterrows():
            duration_days = row.get("duration_days")
            quarter_number = quarter_order[row["fiscal_period"]]
            is_cumulative = (
                row["fiscal_period"] in {"Q2", "Q3"}
                and pd.notna(duration_days)
                and float(duration_days) > 130
            )
            if is_cumulative and completed_quarters != quarter_number - 1:
                # A standalone value cannot be calculated safely when an earlier
                # quarter is missing. Exclude the cumulative row from quarterly reporting.
                rows_to_drop.append(index)
                continue

            if is_cumulative:
                cumulative_value = float(row["value"])
                standalone_value = cumulative_value - prior_standalone_total
                result.at[index, "value"] = standalone_value
                result.at[index, "is_derived"] = True
                result.at[index, "derivation_method"] = (
                    f"{row['fiscal_period']} standalone = fiscal YTD "
                    "- prior standalone quarters"
                )
                if prior_period_end is not None:
                    new_start = pd.Timestamp(prior_period_end) + pd.Timedelta(days=1)
                    result.at[index, "period_start"] = new_start
                    result.at[index, "duration_days"] = (
                        pd.Timestamp(row["period_end"]) - new_start
                    ).days + 1
                standalone_for_sum = standalone_value
            else:
                standalone_for_sum = float(row["value"])

            prior_standalone_total += standalone_for_sum
            prior_period_end = row["period_end"]
            completed_quarters += 1

        if rows_to_drop:
            result = result.drop(index=rows_to_drop)

    return result


def _derive_fourth_quarter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    generated: list[dict[str, Any]] = []
    derivable = {metric.code for metric in METRICS if metric.derive_q4 and not metric.instant}
    for (company_cik, metric_code, fiscal_year, unit), group in df[
        df["metric_code"].isin(derivable)
    ].groupby(["company_cik", "metric_code", "fiscal_year", "unit"]):
        annual = group[(group["period_type"] == "Annual") & (group["fiscal_period"] == "FY")]
        quarters = group[
            (group["period_type"] == "Quarterly")
            & group["fiscal_period"].isin(["Q1", "Q2", "Q3"])
        ]
        if annual.empty or set(quarters["fiscal_period"]) != {"Q1", "Q2", "Q3"}:
            continue
        existing_q4 = group[
            (group["period_type"] == "Quarterly")
            & (group["fiscal_period"] == "Q4")
        ]
        if not existing_q4.empty:
            continue

        annual_row = annual.sort_values("filed_date", ascending=False).iloc[0]
        quarter_rows = quarters.sort_values("filed_date", ascending=False).drop_duplicates(
            subset=["fiscal_period"], keep="first"
        )
        if len(quarter_rows) != 3:
            continue

        q4_value = float(annual_row["value"] - quarter_rows["value"].sum())
        q3_row = quarter_rows[quarter_rows["fiscal_period"] == "Q3"].iloc[0]
        q4_start = pd.Timestamp(q3_row["period_end"]) + pd.Timedelta(days=1)
        q4_duration = (pd.Timestamp(annual_row["period_end"]) - q4_start).days + 1
        generated.append(
            {
                **annual_row.to_dict(),
                "value": q4_value,
                "period_start": q4_start,
                "duration_days": q4_duration,
                "period_type": "Quarterly",
                "fiscal_period": "Q4",
                "form_type": "10-K",
                "is_derived": True,
                "derivation_method": "Q4 = FY - Q1 - Q2 - Q3",
                "accession_number": annual_row["accession_number"],
                "source_url": annual_row["source_url"],
            }
        )

    if not generated:
        return df
    generated_df = pd.DataFrame(generated).dropna(axis=1, how="all")
    return pd.concat([df, generated_df], ignore_index=True)


def _add_q4_instant_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    instant_codes = {metric.code for metric in METRICS if metric.instant}
    generated: list[dict[str, Any]] = []
    annual_instants = df[
        (df["metric_code"].isin(instant_codes))
        & (df["period_type"] == "Annual")
        & (df["fiscal_period"] == "FY")
    ]
    for _, annual_row in annual_instants.iterrows():
        existing_q4 = df[
            (df["company_cik"] == annual_row["company_cik"])
            & (df["metric_code"] == annual_row["metric_code"])
            & (df["fiscal_year"] == annual_row["fiscal_year"])
            & (df["fiscal_period"] == "Q4")
            & (df["period_type"] == "Quarterly")
            & (df["unit"] == annual_row["unit"])
        ]
        if not existing_q4.empty:
            continue
        generated.append(
            {
                **annual_row.to_dict(),
                "period_type": "Quarterly",
                "fiscal_period": "Q4",
                "is_derived": True,
                "derivation_method": "Q4 ending balance = fiscal year-end balance",
            }
        )

    if not generated:
        return df
    generated_df = pd.DataFrame(generated).dropna(axis=1, how="all")
    return pd.concat([df, generated_df], ignore_index=True)


def transform_company_facts(
    payload: dict[str, Any], history_years: int = 10, as_of_year: int | None = None
) -> pd.DataFrame:
    """Transform SEC Company Facts JSON into a curated long-form financial fact table."""
    rows: list[dict[str, Any]] = []
    for metric in METRICS:
        for priority, tag in enumerate(metric.tags):
            rows.extend(_candidate_rows(payload, metric, tag, priority))

    if not rows:
        return pd.DataFrame(columns=FACT_COLUMNS)

    df = _deduplicate(pd.DataFrame(rows))
    df = _normalize_cumulative_quarters(df)
    df = _derive_fourth_quarter(df)
    df = _add_q4_instant_snapshots(df)

    current_year = as_of_year or datetime.utcnow().year
    minimum_fiscal_year = current_year - history_years + 1
    df = df[df["fiscal_year"] >= minimum_fiscal_year].copy()

    df["filed_date"] = pd.to_datetime(df["filed_date"]).dt.date
    df["period_start"] = pd.to_datetime(df["period_start"]).dt.date
    df["period_end"] = pd.to_datetime(df["period_end"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value", "period_end", "metric_code"])

    records = df.to_dict(orient="records")
    for record in records:
        record["business_key"] = _business_key(record)
    df = pd.DataFrame(records)

    df = df.sort_values(
        ["fiscal_year", "period_type", "fiscal_period", "statement_name", "metric_code"]
    ).reset_index(drop=True)
    LOGGER.info("Transformed %s curated financial facts", len(df))
    return df[FACT_COLUMNS]
