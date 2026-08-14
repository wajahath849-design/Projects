"""Profile the immutable raw data-center CSVs and write Step 2 evidence.

The evaluation/private directory is deliberately outside every input path used here.
This script measures quality; it does not clean or overwrite source data.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TABLE_CONFIG = {
    "facilities": {
        "primary_key": ["facility_id"],
        "grain": ["facility_id"],
        "dates": ["commission_date"],
    },
    "servers": {
        "primary_key": ["server_id"],
        "grain": ["server_id"],
        "dates": ["install_date"],
    },
    "server_metrics": {
        "primary_key": ["metric_id"],
        "grain": ["server_id", "timestamp"],
        "dates": ["timestamp"],
    },
    "power_metrics": {
        "primary_key": ["metric_id"],
        "grain": ["facility_id", "timestamp"],
        "dates": ["timestamp"],
    },
    "network_metrics": {
        "primary_key": ["metric_id"],
        "grain": ["facility_id", "timestamp"],
        "dates": ["timestamp"],
    },
    "uptime_incidents": {
        "primary_key": ["incident_id"],
        "grain": ["incident_id"],
        "dates": ["start_time", "end_time"],
    },
}

RANGE_RULES = {
    "facilities": {
        "capacity_mw": (0, None),
        "rack_capacity": (1, None),
        "build_year": (1950, 2025),
    },
    "servers": {"cpu_cores": (1, None), "memory_gb": (1, None)},
    "server_metrics": {
        "cpu_utilization_pct": (0, 100),
        "memory_utilization_pct": (0, 100),
        "disk_utilization_pct": (0, 100),
        "network_utilization_pct": (0, 100),
    },
    "power_metrics": {
        "power_draw_kw": (0, None),
        "it_load_kw": (0, None),
        "cooling_power_kw": (0, None),
        "pue": (1, 2.0),
        "cooling_cost": (0, None),
    },
    "network_metrics": {
        "bandwidth_utilization_pct": (0, 100),
        "latency_ms": (0, None),
        "packet_loss_pct": (0, 5),
        "throughput_mbps": (0, None),
        "network_availability_pct": (0, 100),
    },
    "uptime_incidents": {"downtime_minutes": (0, None)},
}

FOREIGN_KEYS = [
    ("servers", "facility_id", "facilities", "facility_id"),
    ("server_metrics", "server_id", "servers", "server_id"),
    ("power_metrics", "facility_id", "facilities", "facility_id"),
    ("network_metrics", "facility_id", "facilities", "facility_id"),
    ("uptime_incidents", "facility_id", "facilities", "facility_id"),
    ("uptime_incidents", "server_id", "servers", "server_id"),
]


def python_value(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def read_tables(raw_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        name: pd.read_csv(raw_dir / f"{name}.csv", low_memory=False)
        for name in TABLE_CONFIG
    }


def duplicate_summary(frame: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    mask = frame.duplicated(columns, keep=False)
    extra_rows = int(frame.duplicated(columns, keep="first").sum())
    return {
        "columns": columns,
        "affected_rows": int(mask.sum()),
        "extra_rows": extra_rows,
        "extra_row_rate_pct": round(extra_rows / len(frame) * 100, 6),
    }


def numeric_profile(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for column in frame.select_dtypes(include="number").columns:
        series = frame[column]
        result[column] = {
            "count": int(series.count()),
            "min": python_value(series.min()),
            "p25": python_value(series.quantile(0.25)),
            "median": python_value(series.median()),
            "p75": python_value(series.quantile(0.75)),
            "p99": python_value(series.quantile(0.99)),
            "max": python_value(series.max()),
            "mean": python_value(series.mean()),
        }
    return result


def table_profile(name: str, frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    config = TABLE_CONFIG[name]
    date_ranges = {}
    invalid_dates = {}
    for column in config["dates"]:
        parsed = pd.to_datetime(frame[column], errors="coerce")
        date_ranges[column] = {
            "min": python_value(parsed.min()),
            "max": python_value(parsed.max()),
        }
        invalid_dates[column] = int(parsed.isna().sum() - frame[column].isna().sum())

    categorical = {}
    for column in frame.select_dtypes(exclude="number").columns:
        if column not in config["dates"] and frame[column].nunique(dropna=False) <= 25:
            categorical[column] = {
                str(key): int(value)
                for key, value in frame[column].value_counts(dropna=False).items()
            }

    invalid_ranges = {}
    for column, (minimum, maximum) in RANGE_RULES[name].items():
        series = pd.to_numeric(frame[column], errors="coerce")
        invalid = pd.Series(False, index=frame.index)
        if minimum is not None:
            invalid |= series < minimum
        if maximum is not None:
            invalid |= series > maximum
        invalid_ranges[column] = {
            "count": int(invalid.sum()),
            "rate_pct": round(float(invalid.mean() * 100), 6),
            "rule": f"{minimum if minimum is not None else '-inf'} <= value <= {maximum if maximum is not None else 'inf'}",
        }

    null_counts = frame.isna().sum()
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        "nulls": {
            column: {
                "count": int(count),
                "rate_pct": round(float(count / len(frame) * 100), 6),
            }
            for column, count in null_counts.items()
            if count
        },
        "exact_duplicates": duplicate_summary(frame, list(frame.columns)),
        "primary_key_duplicates": duplicate_summary(frame, config["primary_key"]),
        "grain_duplicates": duplicate_summary(frame, config["grain"]),
        "date_ranges": date_ranges,
        "invalid_dates": invalid_dates,
        "invalid_ranges": invalid_ranges,
        "categorical_values": categorical,
        "numeric_profile": numeric_profile(frame),
    }


def temporal_checks(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    expected_dates = pd.date_range("2015-01-01", "2025-12-31", freq="D")
    results = {"expected_daily_dates": int(len(expected_dates))}
    for name, entity_column in (
        ("server_metrics", "server_id"),
        ("power_metrics", "facility_id"),
        ("network_metrics", "facility_id"),
    ):
        frame = tables[name].drop_duplicates([entity_column, "timestamp"])
        frame_dates = pd.to_datetime(frame["timestamp"], errors="coerce")
        counts = frame.assign(_date=frame_dates).groupby(entity_column)["_date"].nunique()
        expected_entities = tables["servers"] if entity_column == "server_id" else tables["facilities"]
        results[name] = {
            "entities_expected": int(expected_entities[entity_column].nunique()),
            "entities_observed": int(counts.size),
            "min_unique_dates_per_entity": int(counts.min()),
            "max_unique_dates_per_entity": int(counts.max()),
            "entities_with_incomplete_daily_coverage": int((counts != len(expected_dates)).sum()),
        }
    return results


def issue_distribution_by_year(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name in ("server_metrics", "power_metrics", "network_metrics"):
        frame = tables[name].copy()
        years = pd.to_datetime(frame["timestamp"], errors="coerce").dt.year
        duplicate_extra = frame.duplicated(TABLE_CONFIG[name]["grain"], keep="first")
        missing_cells = frame.isna().sum(axis=1)
        invalid_cells = pd.Series(0, index=frame.index, dtype="int64")
        for column, (minimum, maximum) in RANGE_RULES[name].items():
            series = pd.to_numeric(frame[column], errors="coerce")
            if minimum is not None:
                invalid_cells += (series < minimum).astype("int64")
            if maximum is not None:
                invalid_cells += (series > maximum).astype("int64")
        yearly = pd.DataFrame(
            {
                "year": years,
                "missing_cells": missing_cells,
                "duplicate_extra_rows": duplicate_extra.astype("int64"),
                "invalid_range_cells": invalid_cells,
            }
        ).groupby("year", dropna=False).sum()
        results[name] = {
            str(int(year)): {column: int(value) for column, value in row.items()}
            for year, row in yearly.iterrows()
        }
    return results


def integrity_checks(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    results = []
    for child, child_column, parent, parent_column in FOREIGN_KEYS:
        values = tables[child][child_column]
        parent_values = set(tables[parent][parent_column].dropna())
        orphan_mask = values.notna() & ~values.isin(parent_values)
        results.append(
            {
                "relationship": f"{child}.{child_column} -> {parent}.{parent_column}",
                "blank_rows": int(values.isna().sum()),
                "orphan_rows": int(orphan_mask.sum()),
                "orphan_rate_pct": round(float(orphan_mask.mean() * 100), 6),
            }
        )
    return results


def consistency_checks(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    servers = tables["servers"]
    incidents = tables["uptime_incidents"]
    power = tables["power_metrics"]

    server_status = servers["status"].astype(str)
    incident_status = incidents["status"].astype(str)
    start = pd.to_datetime(incidents["start_time"], errors="coerce")
    end = pd.to_datetime(incidents["end_time"], errors="coerce")
    duration = (end - start).dt.total_seconds() / 60

    return {
        "servers_noncanonical_status_rows": int((server_status != server_status.str.lower()).sum()),
        "incidents_noncanonical_status_rows": int((incident_status != "resolved").sum()),
        "incident_end_before_start_rows": int((end < start).sum()),
        "incident_duration_mismatch_rows": int((duration != incidents["downtime_minutes"]).sum()),
        "power_draw_below_it_load_rows": int((power["power_draw_kw"] < power["it_load_kw"]).sum()),
        "commission_before_build_rows": int(
            (
                pd.to_datetime(tables["facilities"]["commission_date"]).dt.year
                < tables["facilities"]["build_year"]
            ).sum()
        ),
    }


def build_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    tables = report["tables"]
    return [
        {
            "id": "DQ-001",
            "severity": "high",
            "finding": "Duplicate fact measurements violate primary-key and natural-grain uniqueness.",
            "evidence": {
                name: tables[name]["primary_key_duplicates"]["extra_rows"]
                for name in ("server_metrics", "power_metrics", "network_metrics")
            },
            "risk": "Aggregations can be overstated and database primary-key loads can fail.",
            "recommended_step3_action": "Deterministically retain one row per metric_id and verify natural-grain uniqueness.",
        },
        {
            "id": "DQ-002",
            "severity": "high",
            "finding": "Required analytical measures contain missing values.",
            "evidence": {
                name: sum(item["count"] for item in tables[name]["nulls"].values())
                for name in ("server_metrics", "power_metrics", "network_metrics")
            },
            "risk": "Averages and totals can silently use different denominators.",
            "recommended_step3_action": "Impute only with documented, group-aware rules and record affected rows.",
        },
        {
            "id": "DQ-003",
            "severity": "high",
            "finding": "CPU and memory percentages exceed their physical 0–100% domain.",
            "evidence": {
                column: tables["server_metrics"]["invalid_ranges"][column]["count"]
                for column in ("cpu_utilization_pct", "memory_utilization_pct")
            },
            "risk": "Capacity and hotspot analysis would be biased upward.",
            "recommended_step3_action": "Replace injected extremes using a reproducible robust rule; do not merely hide them in charts.",
        },
        {
            "id": "DQ-004",
            "severity": "high",
            "finding": "PUE and packet-loss values exceed conservative operational validity thresholds.",
            "evidence": {
                "pue_above_2_0": tables["power_metrics"]["invalid_ranges"]["pue"]["count"],
                "packet_loss_above_5_pct": tables["network_metrics"]["invalid_ranges"]["packet_loss_pct"]["count"],
            },
            "risk": "Energy and network anomaly rankings can be dominated by injected errors.",
            "recommended_step3_action": "Flag and repair with documented domain rules, retaining an audit trail.",
        },
        {
            "id": "DQ-005",
            "severity": "medium",
            "finding": "Status labels use inconsistent casing and synonyms.",
            "evidence": report["consistency"],
            "risk": "Category counts split logically identical states across dashboard filters.",
            "recommended_step3_action": "Normalize server status to lowercase and incident completion synonyms to resolved.",
        },
        {
            "id": "DQ-006",
            "severity": "low",
            "finding": "Referential integrity and daily coverage are complete after deduplicating the natural grain.",
            "evidence": {
                "foreign_key_orphan_rows": sum(item["orphan_rows"] for item in report["referential_integrity"]),
                "temporal": report["temporal_coverage"],
            },
            "risk": "No current join-coverage or calendar-gap remediation is required.",
            "recommended_step3_action": "Preserve these checks as regression tests.",
        },
    ]


def profile(raw_dir: Path) -> dict[str, Any]:
    tables = read_tables(raw_dir)
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "raw data only; evaluation/private excluded",
        "assumptions": {
            "operational_period": ["2015-01-01", "2025-12-31"],
            "pue_validity_rule": "1.0 to 2.0 for this synthetic canonical dataset",
            "packet_loss_validity_rule": "0% to 5% for this synthetic canonical dataset",
            "percentage_rule": "0% to 100%",
        },
        "tables": {
            name: table_profile(name, frame, raw_dir / f"{name}.csv")
            for name, frame in tables.items()
        },
        "referential_integrity": integrity_checks(tables),
        "temporal_coverage": temporal_checks(tables),
        "issue_distribution_by_year": issue_distribution_by_year(tables),
        "consistency": consistency_checks(tables),
    }
    report["findings"] = build_findings(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the Step 2 raw-data quality profile.")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("docs/step2_data_quality_profile.json"))
    args = parser.parse_args()
    result = profile(args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
