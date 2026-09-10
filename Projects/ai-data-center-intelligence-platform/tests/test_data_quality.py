from pathlib import Path

from scripts.profile_data import profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT = profile(PROJECT_ROOT / "data" / "raw")


def test_expected_raw_row_counts() -> None:
    expected = {
        "facilities": 6,
        "servers": 430,
        "server_metrics": 1_728_054,
        "power_metrics": 24_123,
        "network_metrics": 24_121,
        "uptime_incidents": 1_158,
    }
    assert {name: item["rows"] for name, item in REPORT["tables"].items()} == expected


def test_injected_duplicate_counts_are_detected() -> None:
    expected = {"server_metrics": 314, "power_metrics": 15, "network_metrics": 13}
    actual = {
        name: REPORT["tables"][name]["primary_key_duplicates"]["extra_rows"]
        for name in expected
    }
    assert actual == expected


def test_injected_missing_value_counts_are_detected() -> None:
    expected = {"server_metrics": 1_373, "power_metrics": 72, "network_metrics": 92}
    actual = {
        name: sum(value["count"] for value in REPORT["tables"][name]["nulls"].values())
        for name in expected
    }
    assert actual == expected


def test_domain_outliers_are_detected() -> None:
    tables = REPORT["tables"]
    assert tables["server_metrics"]["invalid_ranges"]["cpu_utilization_pct"]["count"] == 343
    assert tables["server_metrics"]["invalid_ranges"]["memory_utilization_pct"]["count"] == 343
    assert tables["power_metrics"]["invalid_ranges"]["pue"]["count"] == 25
    assert tables["network_metrics"]["invalid_ranges"]["packet_loss_pct"]["count"] == 25


def test_referential_integrity_has_no_orphans() -> None:
    assert all(item["orphan_rows"] == 0 for item in REPORT["referential_integrity"])


def test_daily_natural_grain_coverage_is_complete_after_deduplication() -> None:
    for table in ("server_metrics", "power_metrics", "network_metrics"):
        assert REPORT["temporal_coverage"][table]["entities_with_incomplete_daily_coverage"] == 0


def test_incident_duration_is_consistent() -> None:
    assert REPORT["consistency"]["incident_end_before_start_rows"] == 0
    assert REPORT["consistency"]["incident_duration_mismatch_rows"] == 0
