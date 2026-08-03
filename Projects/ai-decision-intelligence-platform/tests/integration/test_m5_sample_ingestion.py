"""Live SQL Server verification for the synthetic Phase 2 sample."""

from pathlib import Path

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "SYNTHETIC_M5_SAMPLE"
VERSION = "sample-v1"


def test_sample_fact_row_counts_match_expected_grain() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        sales = fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactSales WHERE SourceSystem=? AND DataVersion=?",
            SOURCE,
            VERSION,
        )
        prices = fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.FactSellPrice WHERE SourceSystem=? AND DataVersion=?",
            SOURCE,
            VERSION,
        )
    assert int(sales) == 224
    assert int(prices) == 224


def test_sample_identifiers_and_date_range_are_valid() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        products = fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.DimProduct WHERE SourceSystem=? AND DataVersion=?",
            SOURCE,
            VERSION,
        )
        stores = fetch_scalar(
            connection,
            "SELECT COUNT(*) FROM dbo.DimStore WHERE SourceSystem=? AND DataVersion=?",
            SOURCE,
            VERSION,
        )
        row = connection.execute(
            """SELECT MIN(d.FullDate), MAX(d.FullDate)
            FROM dbo.FactSales s JOIN dbo.DimDate d ON d.DateKey=s.DateKey
            WHERE s.SourceSystem=? AND s.DataVersion=?""",
            SOURCE,
            VERSION,
        ).fetchone()
    assert int(products) == 4
    assert int(stores) == 2
    assert row is not None
    assert str(row[0]) == "2016-01-01"
    assert str(row[1]) == "2016-01-28"


def test_sample_has_no_orphan_facts() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        orphans = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactSales f
            LEFT JOIN dbo.DimDate d ON d.DateKey=f.DateKey
            LEFT JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
            LEFT JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
            WHERE f.SourceSystem=? AND f.DataVersion=?
              AND (d.DateKey IS NULL OR p.ProductKey IS NULL OR s.StoreKey IS NULL)""",
            SOURCE,
            VERSION,
        )
    assert int(orphans) == 0
