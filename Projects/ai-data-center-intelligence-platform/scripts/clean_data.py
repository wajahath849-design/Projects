"""Reproducibly clean raw CSVs without modifying source or supplied baseline data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


TABLES = (
    "facilities",
    "servers",
    "server_metrics",
    "power_metrics",
    "network_metrics",
    "uptime_incidents",
)

MEASURE_COLUMNS = {
    "server_metrics": [
        "cpu_utilization_pct",
        "memory_utilization_pct",
        "disk_utilization_pct",
        "network_utilization_pct",
    ],
    "power_metrics": [
        "power_draw_kw",
        "it_load_kw",
        "cooling_power_kw",
        "pue",
        "cooling_cost",
    ],
    "network_metrics": [
        "bandwidth_utilization_pct",
        "latency_ms",
        "packet_loss_pct",
        "throughput_mbps",
        "network_availability_pct",
    ],
}


def load_rules(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_categories(tables: dict[str, pd.DataFrame]) -> dict[str, int]:
    changed = {}
    server_status = tables["servers"]["status"].astype("string")
    normalized = server_status.str.strip().str.lower()
    changed["servers.status"] = int((server_status != normalized).sum())
    tables["servers"]["status"] = normalized

    incident_status = tables["uptime_incidents"]["status"].astype("string")
    normalized = incident_status.str.strip().str.lower().replace(
        {"done": "resolved", "closed": "resolved"}
    )
    changed["uptime_incidents.status"] = int((incident_status != normalized).sum())
    tables["uptime_incidents"]["status"] = normalized
    return changed


def validate_allowed_categories(tables: dict[str, pd.DataFrame], rules: dict[str, Any]) -> None:
    for qualified_name, rule in rules["categorical_normalization"].items():
        table, column = qualified_name.split(".")
        unexpected = set(tables[table][column].dropna()) - set(rule["allowed"])
        if unexpected:
            raise ValueError(f"Unexpected values in {qualified_name}: {sorted(unexpected)}")


def deduplicate(tables: dict[str, pd.DataFrame], rules: dict[str, Any]) -> dict[str, int]:
    removed = {}
    keep = rules["deduplication"]["keep"]
    for table, keys in rules["deduplication"]["tables"].items():
        before = len(tables[table])
        tables[table] = (
            tables[table]
            .drop_duplicates(subset=keys, keep=keep)
            .reset_index(drop=True)
            .copy()
        )
        removed[table] = before - len(tables[table])
    return removed


def mark_invalid_as_missing(
    tables: dict[str, pd.DataFrame], rules: dict[str, Any]
) -> dict[str, int]:
    replaced = {}
    for qualified_name, bounds in rules["invalid_to_missing"].items():
        table, column = qualified_name.split(".")
        values = pd.to_numeric(tables[table][column], errors="coerce")
        invalid = values.lt(bounds["minimum"]) | values.gt(bounds["maximum"])
        replaced[qualified_name] = int(invalid.sum())
        tables[table].loc[invalid, column] = np.nan
    return replaced


def impute_time_series(
    tables: dict[str, pd.DataFrame], rules: dict[str, Any]
) -> dict[str, int]:
    counts = {}
    entities = rules["imputation"]["entity_columns"]
    order_column = rules["imputation"]["ordering_column"]

    for table, columns in MEASURE_COLUMNS.items():
        frame = tables[table].sort_values([entities[table], order_column]).copy()
        entity = entities[table]
        for column in columns:
            missing_before = int(frame[column].isna().sum())
            if missing_before == 0:
                counts[f"{table}.{column}"] = 0
                continue

            interpolated = frame.groupby(entity, sort=False)[column].transform(
                lambda values: values.interpolate(method="linear", limit_direction="both")
            )
            entity_median = frame.groupby(entity, sort=False)[column].transform("median")
            frame[column] = interpolated.fillna(entity_median).fillna(frame[column].median())
            counts[f"{table}.{column}"] = missing_before
        tables[table] = frame.sort_index()
    return counts


def apply_rounding(tables: dict[str, pd.DataFrame], rules: dict[str, Any]) -> None:
    default_decimals = int(rules["rounding"]["default_decimals"])
    overrides = rules["rounding"]["columns"]
    for table, columns in MEASURE_COLUMNS.items():
        for column in columns:
            decimals = int(overrides.get(f"{table}.{column}", default_decimals))
            tables[table][column] = tables[table][column].round(decimals)


def clean(raw_dir: Path, rules_path: Path) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    rules = load_rules(rules_path)
    tables = {
        table: pd.read_csv(raw_dir / f"{table}.csv", low_memory=False) for table in TABLES
    }
    audit = {
        "rules_version": str(rules["version"]),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_directory": raw_dir.as_posix(),
        "rows_before": {table: int(len(frame)) for table, frame in tables.items()},
    }
    audit["duplicates_removed"] = deduplicate(tables, rules)
    audit["categories_normalized"] = normalize_categories(tables)
    validate_allowed_categories(tables, rules)
    audit["invalid_values_marked_missing"] = mark_invalid_as_missing(tables, rules)
    audit["values_imputed"] = impute_time_series(tables, rules)
    apply_rounding(tables, rules)
    audit["rows_after"] = {table: int(len(frame)) for table, frame in tables.items()}
    return tables, audit


def compare_with_baseline(
    generated: dict[str, pd.DataFrame], baseline_dir: Path
) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for table, actual in generated.items():
        expected = pd.read_csv(baseline_dir / f"{table}.csv", low_memory=False)
        item: dict[str, Any] = {
            "row_count_equal": len(actual) == len(expected),
            "column_order_equal": list(actual.columns) == list(expected.columns),
            "columns": {},
        }
        if len(actual) != len(expected) or list(actual.columns) != list(expected.columns):
            comparison[table] = item
            continue
        for column in actual.columns:
            left = actual[column]
            right = expected[column]
            if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
                equal = np.isclose(left, right, rtol=0, atol=10 ** -10, equal_nan=True)
                mismatches = int((~equal).sum())
                differences = (left - right).abs()
                item["columns"][column] = {
                    "mismatched_cells": mismatches,
                    "match_rate_pct": round(float(equal.mean() * 100), 6),
                    "mae_on_mismatches": (
                        round(float(differences[~equal].mean()), 6) if mismatches else 0.0
                    ),
                    "max_abs_difference": (
                        round(float(differences[~equal].max()), 6) if mismatches else 0.0
                    ),
                }
            else:
                equal = left.fillna("<NULL>").astype(str).eq(
                    right.fillna("<NULL>").astype(str)
                )
                item["columns"][column] = {
                    "mismatched_cells": int((~equal).sum()),
                    "match_rate_pct": round(float(equal.mean() * 100), 6),
                }
        comparison[table] = item
    return comparison


def write_outputs(tables: dict[str, pd.DataFrame], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for table, frame in tables.items():
        frame.to_csv(output_dir / f"{table}.csv", index=False, lineterminator="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean raw data and compare with baseline.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/cleaned_generated"))
    parser.add_argument("--baseline-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--rules", type=Path, default=Path("config/cleaning_rules.yaml"))
    parser.add_argument("--audit", type=Path, default=Path("docs/step3_cleaning_audit.json"))
    args = parser.parse_args()

    tables, audit = clean(args.raw_dir, args.rules)
    write_outputs(tables, args.output_dir)
    audit["output_directory"] = args.output_dir.as_posix()
    audit["baseline_comparison"] = compare_with_baseline(tables, args.baseline_dir)
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"Wrote {len(tables)} cleaned CSVs to {args.output_dir}")
    print(f"Wrote audit report to {args.audit}")


if __name__ == "__main__":
    main()
