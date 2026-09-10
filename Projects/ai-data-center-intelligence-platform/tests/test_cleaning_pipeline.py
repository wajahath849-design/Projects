from pathlib import Path

import pandas as pd
import pytest

from scripts.clean_data import TABLES, clean, compare_with_baseline, write_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cleaned():
    return clean(
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "config" / "cleaning_rules.yaml",
    )


def test_expected_duplicate_rows_are_removed(cleaned) -> None:
    _, audit = cleaned
    assert audit["duplicates_removed"] == {
        "server_metrics": 314,
        "power_metrics": 15,
        "network_metrics": 13,
    }


def test_cleaned_tables_have_no_missing_values(cleaned) -> None:
    tables, _ = cleaned
    assert all(int(frame.isna().sum().sum()) == 0 for frame in tables.values())


def test_primary_and_natural_grains_are_unique(cleaned) -> None:
    tables, _ = cleaned
    assert tables["facilities"]["facility_id"].is_unique
    assert tables["servers"]["server_id"].is_unique
    assert tables["server_metrics"]["metric_id"].is_unique
    assert not tables["server_metrics"].duplicated(["server_id", "timestamp"]).any()
    assert tables["power_metrics"]["metric_id"].is_unique
    assert not tables["power_metrics"].duplicated(["facility_id", "timestamp"]).any()
    assert tables["network_metrics"]["metric_id"].is_unique
    assert not tables["network_metrics"].duplicated(["facility_id", "timestamp"]).any()
    assert tables["uptime_incidents"]["incident_id"].is_unique


def test_values_conform_to_cleaning_domains(cleaned) -> None:
    tables, _ = cleaned
    server = tables["server_metrics"]
    for column in (
        "cpu_utilization_pct",
        "memory_utilization_pct",
        "disk_utilization_pct",
        "network_utilization_pct",
    ):
        assert server[column].between(0, 100).all()
    assert tables["power_metrics"]["pue"].between(1, 2).all()
    assert tables["network_metrics"]["packet_loss_pct"].between(0, 5).all()


def test_categories_are_canonical(cleaned) -> None:
    tables, _ = cleaned
    assert set(tables["servers"]["status"]) <= {
        "active",
        "maintenance",
        "decommissioned",
    }
    assert set(tables["uptime_incidents"]["status"]) == {"resolved"}


def test_foreign_keys_resolve(cleaned) -> None:
    tables, _ = cleaned
    facilities = set(tables["facilities"]["facility_id"])
    servers = set(tables["servers"]["server_id"])
    assert set(tables["servers"]["facility_id"]) <= facilities
    assert set(tables["server_metrics"]["server_id"]) <= servers
    assert set(tables["power_metrics"]["facility_id"]) <= facilities
    assert set(tables["network_metrics"]["facility_id"]) <= facilities
    assert set(tables["uptime_incidents"]["facility_id"]) <= facilities
    assert set(tables["uptime_incidents"]["server_id"]) <= servers


def test_output_round_trip_preserves_schema_and_rows(cleaned, tmp_path) -> None:
    tables, _ = cleaned
    write_outputs(tables, tmp_path)
    for table in TABLES:
        loaded = pd.read_csv(tmp_path / f"{table}.csv")
        assert list(loaded.columns) == list(tables[table].columns)
        assert len(loaded) == len(tables[table])


def test_baseline_has_same_shape_and_only_repaired_values_can_differ(cleaned) -> None:
    tables, audit = cleaned
    comparison = compare_with_baseline(tables, PROJECT_ROOT / "data" / "processed")
    assert all(item["row_count_equal"] for item in comparison.values())
    assert all(item["column_order_equal"] for item in comparison.values())

    expected_possible_differences = {
        **audit["values_imputed"],
        **audit["invalid_values_marked_missing"],
        **audit["categories_normalized"],
    }
    for table, item in comparison.items():
        for column, result in item["columns"].items():
            qualified = f"{table}.{column}"
            if qualified not in expected_possible_differences:
                assert result["mismatched_cells"] == 0, qualified
