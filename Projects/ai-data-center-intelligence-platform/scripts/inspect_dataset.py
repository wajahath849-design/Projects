"""Read-only structural inspection for the canonical data-center dataset.

This script intentionally never opens evaluation/private or reads anomaly answers.
It uses only the Python standard library so it can verify a fresh environment.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PRIMARY_KEYS = {
    "facilities.csv": "facility_id",
    "servers.csv": "server_id",
    "server_metrics.csv": "metric_id",
    "power_metrics.csv": "metric_id",
    "network_metrics.csv": "metric_id",
    "uptime_incidents.csv": "incident_id",
}

DATE_COLUMNS = {
    "facilities.csv": ("commission_date",),
    "servers.csv": ("install_date",),
    "server_metrics.csv": ("timestamp",),
    "power_metrics.csv": ("timestamp",),
    "network_metrics.csv": ("timestamp",),
    "uptime_incidents.csv": ("start_time", "end_time"),
}


def inspect_csv(path: Path) -> dict[str, object]:
    primary_key = PRIMARY_KEYS[path.name]
    date_columns = DATE_COLUMNS[path.name]
    row_count = 0
    duplicate_keys = 0
    seen_keys: set[str] = set()
    date_ranges = {column: [None, None] for column in date_columns}

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        blank_cells = {column: 0 for column in columns}

        for row in reader:
            row_count += 1
            for column, value in row.items():
                if value is None or not value.strip():
                    blank_cells[column] += 1

            key = row.get(primary_key, "")
            if key in seen_keys:
                duplicate_keys += 1
            else:
                seen_keys.add(key)

            for column in date_columns:
                value = row.get(column, "").strip()
                if not value:
                    continue
                minimum, maximum = date_ranges[column]
                date_ranges[column][0] = value if minimum is None or value < minimum else minimum
                date_ranges[column][1] = value if maximum is None or value > maximum else maximum

    return {
        "rows": row_count,
        "columns": columns,
        "size_bytes": path.stat().st_size,
        "blank_cells": {key: value for key, value in blank_cells.items() if value},
        "duplicate_primary_key_values": duplicate_keys,
        "date_ranges": date_ranges,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect raw and processed dataset structure.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    args = parser.parse_args()

    report: dict[str, object] = {}
    for layer in ("raw", "processed"):
        folder = args.data_root / layer
        report[layer] = {
            filename: inspect_csv(folder / filename) for filename in PRIMARY_KEYS
        }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
