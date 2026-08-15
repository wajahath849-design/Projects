import pandas as pd

from src.dataset_adapter import DatasetAdapter


def adapter():
    return DatasetAdapter("analytics/canonical_data_contract.json", "adapters/default_aliases.json")


def test_alias_mapping_and_generated_metric_id():
    source = pd.DataFrame({
        "data_center_id": ["FAC-001"], "date": ["2025-01-01"],
        "power_usage_effectiveness": [1.3], "total_power_kw": [100.0],
    })
    result = adapter().adapt_table(source, "power_metrics")
    assert result.mapping["data_center_id"] == "facility_id"
    assert result.frame.loc[0, "metric_id"].startswith("GEN-")


def test_partial_power_only_module_can_be_adapted():
    source = pd.read_csv("data/processed/power_metrics.csv").rename(columns={"facility_id": "site_id", "timestamp": "date"})
    result = adapter().adapt_table(source, "power_metrics")
    assert len(result.frame) == len(source)
    assert {"facility_id", "timestamp", "pue"} <= set(result.frame)
