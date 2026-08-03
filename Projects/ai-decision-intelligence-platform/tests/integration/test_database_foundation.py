"""Integration checks against the configured SQL Server database."""

from pathlib import Path

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.database.initializer import verify_database
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_database_foundation_is_complete() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    result = verify_database(settings)
    assert result.passed, result.failures


def test_foreign_key_rejects_invalid_product() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        try:
            connection.execute(
                "INSERT dbo.FactSales (DateKey, ProductKey, StoreKey, Quantity) "
                "VALUES (20260101, -999999, -999999, 1)"
            )
        except Exception as exc:
            assert "FOREIGN KEY" in str(exc).upper()
        else:
            raise AssertionError("Invalid foreign keys were accepted")
        finally:
            connection.rollback()


def test_power_bi_views_are_queryable() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        count = fetch_scalar(connection, "SELECT COUNT(*) FROM dbo.vw_ExecutiveOverview")
        assert int(count) >= 1
