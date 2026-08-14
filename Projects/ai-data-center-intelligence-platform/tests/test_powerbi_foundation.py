from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
POWERBI = PROJECT_ROOT / "powerbi"


def test_all_power_query_sources_exist() -> None:
    names = {path.stem for path in (POWERBI / "foundation" / "PowerQuery").glob("*.pq")}
    assert names == {
        "DataRoot", "DimFacility", "DimServer", "FactServerMetrics",
        "FactPowerMetrics", "FactNetworkMetrics", "FactIncidents",
    }


def test_foundational_dax_contains_canonical_measures() -> None:
    dax = (POWERBI / "foundation" / "DAX" / "measures.dax").read_text(encoding="utf-8")
    required = [
        "Average PUE", "Total Power Draw", "Total Cooling Cost", "Total Downtime",
        "Incident Count", "Active Server Count", "Average CPU Utilization",
        "Average Memory Utilization", "Average Network Latency", "Average Packet Loss",
        "Network Availability", "Downtime per Server", "Incident Rate per 100 Servers",
        "Year-over-Year PUE Change", "Year-over-Year Cooling Cost Change",
        "Year-over-Year Downtime Change",
    ]
    assert all(f"{name} =" in dax for name in required)


def test_date_table_uses_canonical_dataset_range() -> None:
    dax = (POWERBI / "foundation" / "DAX" / "calculated_tables.dax").read_text(encoding="utf-8")
    assert "DATE(2015, 1, 1)" in dax
    assert "DATE(2025, 12, 31)" in dax


def test_power_query_uses_verified_processed_data() -> None:
    parameter = (POWERBI / "foundation" / "PowerQuery" / "DataRoot.pq").read_text(encoding="utf-8")
    assert "data\\\\processed" in parameter


def test_generated_pbip_has_three_pages_and_model_files() -> None:
    root = POWERBI / "PBI"
    assert (root / "DataCenter Operations Foundation.pbip").exists()
    semantic = root / "DataCenter Operations Foundation.SemanticModel" / "definition"
    assert (semantic / "model.tmdl").exists()
    assert (semantic / "relationships.tmdl").exists()
    assert len(list((semantic / "tables").glob("*.tmdl"))) == 8
    pages = root / "DataCenter Operations Foundation.Report" / "definition" / "pages"
    assert len([path for path in pages.iterdir() if path.is_dir()]) == 3


def test_generated_model_has_expected_relationships() -> None:
    path = POWERBI / "PBI" / "DataCenter Operations Foundation.SemanticModel" / "definition" / "relationships.tmdl"
    text = path.read_text(encoding="utf-8")
    assert text.count("relationship ") == 10
    assert "isActive: false" in text


def test_report_pages_use_opaque_internal_ids_and_base_theme() -> None:
    import json

    report_root = POWERBI / "PBI" / "DataCenter Operations Foundation.Report" / "definition"
    pages = json.loads((report_root / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert all(len(name) == 20 and name.isalnum() for name in pages["pageOrder"])
    report = json.loads((report_root / "report.json").read_text(encoding="utf-8"))
    assert report["themeCollection"]["baseTheme"]["name"] == "CY25SU12"
