"""Deterministic analytics engine for auditing ratio-based business claims.

The engine deliberately keeps statistical calculations separate from any language
model. Every sentence returned to the UI is backed by a value computed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import uuid4
from math import erfc, sqrt
from typing import Any

import numpy as np
import pandas as pd


class AuditInputError(ValueError):
    """Raised when a dataset cannot support the requested audit."""


@dataclass(frozen=True)
class AuditSpec:
    metric_name: str
    claim: str
    numerator: str
    denominator: str
    date_column: str
    segment_columns: list[str]
    split_date: str | date | None = None
    audit_id: str | None = None
    source_name: str | None = None


def _native(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_native(item) for item in value]
    if isinstance(value, tuple):
        return [_native(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else round(float(value), 6)
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    return value


def _ratio(frame: pd.DataFrame, numerator: str, denominator: str) -> float:
    denominator_sum = float(frame[denominator].sum())
    if denominator_sum <= 0:
        return 0.0
    return float(frame[numerator].sum()) / denominator_sum


def _change(before: float, after: float) -> tuple[float, float | None]:
    absolute = after - before
    relative = absolute / before if before else None
    return absolute, relative


def _fmt_pp(value: float) -> str:
    return f"{value * 100:+.2f} pp"


def _severity_penalty(severity: str) -> int:
    return {"critical": 28, "high": 22, "medium": 12, "low": 6}.get(severity, 0)


def _finding(
    key: str,
    category: str,
    severity: str,
    title: str,
    summary: str,
    evidence: str,
    recommendation: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": key,
        "category": category,
        "severity": severity,
        "title": title,
        "summary": summary,
        "evidence": evidence,
        "recommendation": recommendation,
        "details": details or {},
    }


def _two_proportion_p_value(
    success_a: float, total_a: float, success_b: float, total_b: float
) -> float:
    if total_a <= 0 or total_b <= 0:
        return 1.0
    pooled = (success_a + success_b) / (total_a + total_b)
    standard_error = sqrt(
        max(pooled * (1 - pooled) * ((1 / total_a) + (1 / total_b)), 0)
    )
    if standard_error == 0:
        return 1.0
    z_score = ((success_b / total_b) - (success_a / total_a)) / standard_error
    return float(erfc(abs(z_score) / sqrt(2)))


def _fixed_mix_rate(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    segment: str,
    numerator: str,
    denominator: str,
) -> tuple[float, float, list[dict[str, Any]]]:
    base = baseline.groupby(segment, dropna=False)[[numerator, denominator]].sum()
    now = current.groupby(segment, dropna=False)[[numerator, denominator]].sum()
    common = base.index.intersection(now.index)
    if common.empty:
        return (
            _ratio(baseline, numerator, denominator),
            _ratio(current, numerator, denominator),
            [],
        )

    base = base.loc[common]
    now = now.loc[common]
    weights = base[denominator] / max(float(base[denominator].sum()), 1.0)
    base_rates = base[numerator] / base[denominator].replace(0, np.nan)
    now_rates = now[numerator] / now[denominator].replace(0, np.nan)
    adjusted_before = float((weights * base_rates.fillna(0)).sum())
    adjusted_after = float((weights * now_rates.fillna(0)).sum())
    rows: list[dict[str, Any]] = []
    current_total = max(float(now[denominator].sum()), 1.0)
    for value in common:
        rows.append(
            {
                "segment": str(value),
                "series_key": "segment:" + str(value),
                "baseline_rate": float(base_rates.loc[value]),
                "current_rate": float(now_rates.loc[value]),
                "baseline_share": float(weights.loc[value]),
                "current_share": float(now.loc[value, denominator] / current_total),
            }
        )
    return adjusted_before, adjusted_after, rows


def _weekly_series(
    frame: pd.DataFrame,
    spec: AuditSpec,
    primary_segment: str | None,
) -> list[dict[str, Any]]:
    work = frame.copy()
    work["_week"] = work[spec.date_column].dt.to_period("W").dt.start_time
    aggregate = work.groupby("_week")[[spec.numerator, spec.denominator]].sum()
    aggregate["rate"] = aggregate[spec.numerator] / aggregate[spec.denominator]

    segment_rates: dict[str, dict[pd.Timestamp, float]] = {}
    if primary_segment:
        grouped = work.groupby(["_week", primary_segment])[
            [spec.numerator, spec.denominator]
        ].sum()
        grouped["rate"] = grouped[spec.numerator] / grouped[spec.denominator]
        for segment_value in grouped.index.get_level_values(1).unique():
            values = grouped.xs(segment_value, level=1)["rate"].to_dict()
            segment_rates[str(segment_value)] = values

    points: list[dict[str, Any]] = []
    for week, row in aggregate.iterrows():
        point: dict[str, Any] = {
            "date": week.date().isoformat(),
            "aggregate": float(row["rate"] * 100),
        }
        for segment_value, values in segment_rates.items():
            if week in values:
                point["segment:" + segment_value] = float(
                    values[week] * 100
                )
        points.append(point)
    return points


def analyze_dataframe(frame: pd.DataFrame, spec: AuditSpec) -> dict[str, Any]:
    mapped = [spec.numerator, spec.denominator, spec.date_column, *spec.segment_columns]
    if len(set(mapped)) != len(mapped):
        raise AuditInputError("Choose different columns for the numerator, denominator, date and segments.")
    required = {
        spec.numerator,
        spec.denominator,
        spec.date_column,
        *spec.segment_columns,
    }
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise AuditInputError(f"Missing required columns: {', '.join(missing_columns)}")
    if frame.empty:
        raise AuditInputError("The dataset is empty.")
    frame = frame.reset_index(drop=True)

    original_rows = len(frame)
    duplicate_rows = int(frame.duplicated().sum())
    work = frame.copy()
    work[spec.date_column] = pd.to_datetime(
        work[spec.date_column], errors="coerce", utc=True
    ).dt.tz_localize(None)
    work[spec.numerator] = pd.to_numeric(work[spec.numerator], errors="coerce")
    work[spec.denominator] = pd.to_numeric(work[spec.denominator], errors="coerce")
    work[[spec.numerator, spec.denominator]] = work[[spec.numerator, spec.denominator]].replace([np.inf, -np.inf], np.nan)
    # Normalize group labels once so mixed numeric/missing labels are stable throughout.
    for column in spec.segment_columns:
        labels = work[column].dropna().astype(str)
        missing_label = "(Missing)"
        while missing_label in set(labels):
            missing_label += " (unknown)"
        work[column] = work[column].map(lambda value: missing_label if pd.isna(value) else str(value))

    invalid_dates = int(work[spec.date_column].isna().sum())
    invalid_values = int(
        (work[spec.numerator].isna() | work[spec.denominator].isna() | (work[spec.numerator] < 0)).sum()
    )
    non_positive_denominators = int((work[spec.denominator] <= 0).sum())
    valid = work[
        work[spec.date_column].notna()
        & work[spec.numerator].notna()
        & work[spec.denominator].notna()
        & (work[spec.denominator] > 0)
        & (work[spec.numerator] >= 0)
    ].copy()
    if len(valid) < 4:
        raise AuditInputError("At least four valid dated observations are required.")

    if spec.split_date:
        try:
            split = pd.to_datetime(spec.split_date, utc=True).tz_localize(None)
            if pd.isna(split):
                raise ValueError("Missing split date")
        except (ValueError, TypeError, OverflowError) as exc:
            raise AuditInputError(
                "Enter a valid split date in YYYY-MM-DD format."
            ) from exc
    else:
        unique_dates = sorted(valid[spec.date_column].dt.normalize().unique())
        split = pd.Timestamp(unique_dates[len(unique_dates) // 2])

    baseline = valid[valid[spec.date_column] < split]
    current = valid[valid[spec.date_column] >= split]
    if baseline.empty or current.empty:
        raise AuditInputError(
            "The split date must leave observations in both comparison periods."
        )

    baseline_rate = _ratio(baseline, spec.numerator, spec.denominator)
    current_rate = _ratio(current, spec.numerator, spec.denominator)
    absolute_change, relative_change = _change(baseline_rate, current_rate)
    overall_direction = np.sign(absolute_change)

    findings: list[dict[str, Any]] = []
    limitations = [
        "This before-and-after comparison does not establish causation or control for seasonality.",
        "The score summarizes detected issues with fixed severity penalties; it is not a calibrated probability that the claim is correct.",
        "Exact duplicate records are flagged but retained; this audit cannot determine whether they represent repeated observations.",
    ]
    invalid_total = original_rows - len(valid)
    if duplicate_rows or invalid_total:
        affected = int((~work.index.isin(valid.index) | frame.duplicated().to_numpy()).sum())
        severity = "medium" if affected / original_rows >= 0.02 else "low"
        findings.append(
            _finding(
                "data-integrity",
                "Data quality",
                severity,
                "Input quality can move the headline",
                f"{affected} questionable rows were identified before analysis.",
                f"{duplicate_rows} duplicates, {invalid_dates} invalid dates, {invalid_values} invalid numeric values and {non_positive_denominators} invalid denominators. Categories can overlap.",
                "Resolve or explicitly document excluded rows before using the result for a consequential decision.",
                {
                    "affected_rows": affected,
                    "valid_rows": len(valid),
                    "total_rows": original_rows,
                },
            )
        )

    primary_segment = spec.segment_columns[0] if spec.segment_columns else None
    fixed_before = baseline_rate
    fixed_after = current_rate
    segment_rows: list[dict[str, Any]] = []
    reversal_detected = False
    mix_shift = 0.0

    if primary_segment:
        complete_segments = set(baseline[primary_segment]) == set(current[primary_segment])
        fixed_before, fixed_after, segment_rows = _fixed_mix_rate(
            baseline, current, primary_segment, spec.numerator, spec.denominator
        )
        segment_directions = [
            np.sign(row["current_rate"] - row["baseline_rate"]) for row in segment_rows
        ]
        reversal_detected = bool(
            complete_segments and overall_direction
            and len(segment_directions) >= 2
            and all(direction == -overall_direction for direction in segment_directions)
        )
        if reversal_detected:
            findings.append(
                _finding(
                    "segment-reversal",
                    "Aggregation risk",
                    "high",
                    "The aggregate trend reverses inside every major segment",
                    f"The overall metric moved {_fmt_pp(absolute_change)}, while each {primary_segment} segment moved in the opposite direction.",
                    "This is a Simpson's-paradox pattern: the headline is being driven by who is in the dataset, not consistent improvement inside the groups.",
                    f"Do not present the aggregate change alone. Report {primary_segment}-level results and a mix-adjusted estimate.",
                    {"segment": primary_segment, "rows": segment_rows},
                )
            )

        if segment_rows:
            mix_shift = 0.5 * sum(
                abs(row["current_share"] - row["baseline_share"])
                for row in segment_rows
            )
            if mix_shift >= 0.10:
                severity = "high" if mix_shift >= 0.30 else "medium"
                largest = max(
                    segment_rows,
                    key=lambda row: abs(row["current_share"] - row["baseline_share"]),
                )
                findings.append(
                    _finding(
                        "mix-shift",
                        "Composition drift",
                        severity,
                        f"The {primary_segment} mix changed materially",
                        f"Population composition shifted by {mix_shift * 100:.1f}% between periods.",
                        f"{largest['segment']} moved from {largest['baseline_share'] * 100:.1f}% to {largest['current_share'] * 100:.1f}% of the denominator.",
                        "Normalize both periods to a fixed segment mix before attributing the change to a product or policy.",
                        {"total_variation_distance": mix_shift, "rows": segment_rows},
                    )
                )

    segments_supported = len(segment_rows) >= 2 and complete_segments
    segment_explanation = (
        f"Reweights current {primary_segment} performance using the baseline composition."
        if segments_supported
        else "Mix adjustment requires at least two groups and the same groups in both periods. Missing or new groups prevent a full-population comparison."
    )
    if not segments_supported:
        limitations.append(segment_explanation)
    if primary_segment:
        limitations.append(
            f"Segment analysis uses {primary_segment} only. Mix adjustment includes groups observed in both periods and renormalizes their weights."
        )
    opposing_segments = bool(
        overall_direction
        and any(
            np.sign(row["current_rate"] - row["baseline_rate"]) == -overall_direction
            for row in segment_rows
        )
    )
    adjusted_absolute, adjusted_relative = _change(fixed_before, fixed_after)

    numerator_a = float(baseline[spec.numerator].sum())
    denominator_a = float(baseline[spec.denominator].sum())
    numerator_b = float(current[spec.numerator].sum())
    denominator_b = float(current[spec.denominator].sum())
    proportions_valid = bool(
        (valid[spec.numerator] <= valid[spec.denominator]).all()
        and (valid[spec.numerator] % 1 == 0).all()
        and (valid[spec.denominator] % 1 == 0).all()
    )
    pooled = (numerator_a + numerator_b) / (denominator_a + denominator_b)
    enough_expected_counts = all(
        total * proportion >= 5
        for total in (denominator_a, denominator_b)
        for proportion in (pooled, 1 - pooled)
    )
    reliability_supported = proportions_valid and enough_expected_counts
    reliability_explanation = (
        "Uses a two-proportion normal approximation, assuming independent binary outcomes and at least five expected successes and failures in each period."
        if reliability_supported
        else "This test requires integer success and trial counts, successes no greater than trials, and at least five expected successes and failures in each period."
    )
    limitations.append(
        "The reliability test assumes independent observations; repeated users and clustered events can violate this assumption."
        if reliability_supported
        else reliability_explanation
    )
    p_value = (
        _two_proportion_p_value(numerator_a, denominator_a, numerator_b, denominator_b)
        if reliability_supported
        else None
    )
    if p_value is not None and p_value >= 0.05:
        findings.append(
            _finding(
                "sample-reliability",
                "Statistical reliability",
                "medium",
                "The observed change is not statistically reliable",
                f"A two-proportion test returned p={p_value:.3f}.",
                "The available sample cannot separate the reported movement from ordinary variation at the 5% level.",
                "Collect more observations or report the uncertainty instead of a definitive increase or decrease.",
            )
        )

    q_low = valid[spec.denominator].quantile(0.01)
    q_high = valid[spec.denominator].quantile(0.99)
    clipped = valid[valid[spec.denominator].between(q_low, q_high)].copy()
    clipped_base = clipped[clipped[spec.date_column] < split]
    clipped_current = clipped[clipped[spec.date_column] >= split]
    outliers_supported = not clipped_base.empty and not clipped_current.empty
    clipped_before = _ratio(clipped_base, spec.numerator, spec.denominator)
    clipped_after = _ratio(clipped_current, spec.numerator, spec.denominator)
    clipped_absolute, _ = _change(clipped_before, clipped_after)
    outlier_gap = abs(clipped_absolute - absolute_change)
    if outliers_supported and outlier_gap > max(abs(absolute_change) * 0.30, 0.005):
        findings.append(
            _finding(
                "outlier-sensitivity",
                "Robustness",
                "medium",
                "Large observations materially change the conclusion",
                f"The reported movement changes by {outlier_gap * 100:.2f} percentage points after trimming denominator extremes.",
                "A small number of high-weight observations have disproportionate influence on the aggregate result.",
                "Show both the raw and robust estimates, then investigate the influential records.",
            )
        )

    score = max(0, 100 - sum(_severity_penalty(item["severity"]) for item in findings))
    stress_tests = [
        {
            "name": "Fixed population mix",
            "status": "not_applicable"
            if not segments_supported
            else "failed"
            if np.sign(adjusted_absolute) != overall_direction and overall_direction
            else "passed",
            "reported": _fmt_pp(absolute_change),
            "challenged": _fmt_pp(adjusted_absolute)
            if segments_supported
            else "Not evaluated",
            "explanation": segment_explanation,
        },
        {
            "name": "Segment consistency",
            "status": "not_applicable"
            if not segments_supported
            else "failed"
            if reversal_detected
            else "warning"
            if opposing_segments
            else "passed",
            "reported": "Aggregate direction",
            "challenged": "Not evaluated"
            if not segments_supported
            else "Opposite inside segments"
            if reversal_detected
            else "Mixed segment directions"
            if opposing_segments
            else "No reversal detected",
            "explanation": "Checks whether the headline direction survives disaggregation."
            if segments_supported
            else segment_explanation,
        },
        {
            "name": "Outlier resistance",
            "status": "not_applicable"
            if not outliers_supported
            else "warning"
            if outlier_gap > max(abs(absolute_change) * 0.30, 0.005)
            else "passed",
            "reported": _fmt_pp(absolute_change),
            "challenged": _fmt_pp(clipped_absolute)
            if outliers_supported
            else "Not evaluated",
            "explanation": "Removes denominator weights below the 1st or above the 99th percentile and recalculates the comparison."
            if outliers_supported
            else "Trimming removes all observations from a comparison period; outlier resistance cannot be evaluated.",
        },
        {
            "name": "Sample reliability",
            "status": "not_applicable"
            if p_value is None
            else "passed"
            if p_value < 0.05
            else "warning",
            "reported": "Significant"
            if p_value is not None and p_value < 0.05
            else "Review",
            "challenged": f"p={p_value:.4f}"
            if p_value is not None
            else "Not evaluated",
            "explanation": reliability_explanation,
        },
        {
            "name": "Input completeness",
            "status": "warning" if invalid_total or duplicate_rows else "passed",
            "reported": f"{original_rows} rows",
            "challenged": f"{len(valid)} valid rows",
            "explanation": "Checks parsing, missing values, denominator validity and exact duplicates.",
        },
    ]
    skipped_tests = sum(test["status"] == "not_applicable" for test in stress_tests)
    review_required = bool(findings) or any(
        test["status"] in {"warning", "failed"} for test in stress_tests
    )
    confidence_band = (
        "High decision risk"
        if score < 60 or any(item["severity"] == "critical" for item in findings)
        else "Needs review"
        if review_required
        else "Limited coverage"
        if skipped_tests
        else "No issues detected"
    )
    if not outliers_supported:
        limitations.append(stress_tests[2]["explanation"])

    headline = {
        "metric_name": spec.metric_name,
        "claim": spec.claim,
        "baseline": baseline_rate,
        "current": current_rate,
        "absolute_change": absolute_change,
        "relative_change": relative_change,
        "adjusted_baseline": fixed_before,
        "adjusted_current": fixed_after,
        "adjusted_absolute_change": adjusted_absolute,
        "adjusted_relative_change": adjusted_relative,
        "split_date": split.date().isoformat(),
        "baseline_label": f"Before {split.date().isoformat()}",
        "current_label": f"From {split.date().isoformat()}",
    }
    verdict = {
        "label": confidence_band,
        "summary": (
            "The headline is directionally misleading after controlling for population composition."
            if reversal_detected
            else "The audit found issues that require review before this comparison supports a decision."
            if review_required
            else "No issues were detected in the applicable checks, but some checks could not be evaluated."
            if skipped_tests
            else "No issues were detected by these automated checks. This does not validate causal attribution."
        ),
        "action": (
            "Pause attribution. Present the segment-level and mix-adjusted result before making a rollout decision."
            if reversal_detected
            else "Review the flagged evidence and limitations before presenting the headline."
            if review_required
            else "Review test coverage and assumptions before relying on this comparison."
        ),
    }

    generated_audit_id = "MM-" + uuid4().hex[:12].upper()
    result = {
        "audit_id": spec.audit_id or generated_audit_id,
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "confidence_score": score,
        "headline": headline,
        "verdict": verdict,
        "contract": {
            "numerator_column": spec.numerator,
            "denominator_column": spec.denominator,
            "date_column": spec.date_column,
            "segment_columns": spec.segment_columns,
            "primary_segment": primary_segment,
            "split_date": split.date().isoformat(),
            "baseline_start": baseline[spec.date_column].min().date().isoformat(),
            "baseline_end": baseline[spec.date_column].max().date().isoformat(),
            "current_start": current[spec.date_column].min().date().isoformat(),
            "current_end": current[spec.date_column].max().date().isoformat(),
            "column_count": len(frame.columns),
            "source_name": spec.source_name,
        },
        "limitations": limitations,
        "findings": findings,
        "stress_tests": stress_tests,
        "segments": segment_rows,
        "time_series": _weekly_series(valid, spec, primary_segment),
        "quality": {
            "total_rows": original_rows,
            "valid_rows": len(valid),
            "duplicate_rows": duplicate_rows,
            "invalid_dates": invalid_dates,
            "invalid_values": invalid_values,
            "invalid_denominators": non_positive_denominators,
        },
        "methodology": {
            "tests_run": len(stress_tests) - skipped_tests,
            "tests_available": len(stress_tests),
            "engine": "Metric Mirage deterministic audit engine v1",
            "ai_used_for_calculation": False,
            "score_interpretation": "Heuristic issue score, not a calibrated probability. Skipped checks do not improve the score or establish confidence.",
        },
    }
    return _native(result)
