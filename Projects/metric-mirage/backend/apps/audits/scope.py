"""Apply explicit upload scope before running the analytics engine."""
import json
from dataclasses import replace

import pandas as pd

from .engine import AuditInputError, AuditSpec, analyze_dataframe


def analyze_scoped(frame, spec: AuditSpec, filters: dict):
    if not isinstance(filters, dict):
        raise AuditInputError("Filters must map columns to selected values.")
    source_rows = len(frame)
    source_columns = len(frame.columns)
    for column, values in filters.items():
        if column not in frame.columns or not isinstance(values, list) or not values:
            raise AuditInputError("Each filter needs an existing column and at least one value.")
        if any(value is not None and not isinstance(value, str) for value in values):
            raise AuditInputError("Filter values must be text or null for missing values.")
        labels = frame[column].astype("string")
        mask = labels.isin([value for value in values if value is not None])
        if None in values:
            mask |= frame[column].isna()
        frame = frame.loc[mask].copy()
    if frame.empty:
        raise AuditInputError("No rows match these filters. Choose more values or remove a filter.")
    groups = spec.segment_columns
    if len(set(groups)) != len(groups) or any(column not in frame.columns for column in groups):
        raise AuditInputError("Choose unique grouping columns from this CSV.")
    if any(column in [spec.numerator, spec.denominator, spec.date_column] for column in groups):
        raise AuditInputError("Grouping columns must differ from the metric and date columns.")
    if len(groups) > 1:
        joint = " × ".join(groups)
        while joint in frame.columns:
            joint += " (combined)"
        frame[joint] = frame[groups].apply(
            lambda row: " · ".join(f"{column}={json.dumps(None if pd.isna(row[column]) else str(row[column]), ensure_ascii=False)}" for column in groups), axis=1
        )
        result = analyze_dataframe(frame, replace(spec, segment_columns=[joint]))
    else:
        result = analyze_dataframe(frame, spec)
    result["contract"].update({
        "segment_columns": groups,
        "grouping_mode": "combined" if len(groups) > 1 else "single",
        "filters": filters,
        "source_rows": source_rows,
        "filtered_rows": len(frame),
        "column_count": source_columns,
    })
    return result
