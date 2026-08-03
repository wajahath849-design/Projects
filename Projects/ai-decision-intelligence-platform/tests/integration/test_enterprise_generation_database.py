"""Live SQL Server integrity tests for Phase 3 synthetic enterprise data."""

from pathlib import Path

from decision_intelligence.database.connection import connect, fetch_scalar
from decision_intelligence.settings import load_settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE = "SYNTHETIC_ENTERPRISE"


def test_enterprise_database_row_counts() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    queries = {
        "suppliers": "SELECT COUNT(*) FROM dbo.DimSupplier WHERE SourceSystem=?",
        "warehouses": "SELECT COUNT(*) FROM dbo.DimWarehouse WHERE SourceSystem=?",
        "supplier_products": "SELECT COUNT(*) FROM dbo.BridgeSupplierProduct WHERE SourceSystem=?",
        "lanes": "SELECT COUNT(*) FROM dbo.FactTransportation WHERE SourceSystem=?",
        "orders": "SELECT COUNT(*) FROM dbo.FactPurchaseOrder WHERE SourceSystem=?",
        "order_lines": "SELECT COUNT(*) FROM dbo.FactPurchaseOrderLine WHERE SourceSystem=?",
        "inventory": "SELECT COUNT(*) FROM dbo.FactInventorySnapshot WHERE SourceSystem=?",
        "constraints": "SELECT COUNT(*) FROM dbo.BusinessConstraint WHERE SourceSystem=?",
    }
    expected = {
        "suppliers": 25,
        "warehouses": 5,
        "supplier_products": 12,
        "lanes": 125,
        "orders": 20,
        "order_lines": 20,
        "inventory": 560,
        "constraints": 6,
    }
    with connect(settings) as connection:
        actual = {
            name: int(fetch_scalar(connection, query, SOURCE)) for name, query in queries.items()
        }
    assert actual == expected


def test_inventory_reconciliation_and_capacity() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        reconciliation_failures = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactInventorySnapshot
            WHERE SourceSystem=? AND ClosingStock <>
              OpeningStock+ReceivedQuantity-SoldQuantity-DamagedQuantity-ReservedQuantityAdjustment""",
            SOURCE,
        )
        capacity_failures = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM (
              SELECT i.DateKey,i.WarehouseKey,SUM(i.ClosingStock) AS Units,
                MAX(w.CapacityUnits) AS Capacity
              FROM dbo.FactInventorySnapshot i
              JOIN dbo.DimWarehouse w ON w.WarehouseKey=i.WarehouseKey
              WHERE i.SourceSystem=? GROUP BY i.DateKey,i.WarehouseKey
              HAVING SUM(i.ClosingStock)>MAX(w.CapacityUnits)) failures""",
            SOURCE,
        )
    assert int(reconciliation_failures) == 0
    assert int(capacity_failures) == 0


def test_supplier_capacity_and_purchase_order_lifecycle() -> None:
    _, settings = load_settings(PROJECT_ROOT)
    with connect(settings) as connection:
        supplier_failures = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.BridgeSupplierProduct
            WHERE SourceSystem=? AND DailyCapacity<MinimumOrderQuantity""",
            SOURCE,
        )
        lifecycle_failures = fetch_scalar(
            connection,
            """SELECT COUNT(*) FROM dbo.FactPurchaseOrder po
            JOIN dbo.FactPurchaseOrderLine line ON line.PurchaseOrderKey=po.PurchaseOrderKey
            WHERE po.SourceSystem=? AND (
              (po.Status='COMPLETED' AND line.ReceivedQuantity<>line.OrderedQuantity) OR
              (po.Status='PARTIAL' AND
                (line.ReceivedQuantity<=0 OR line.ReceivedQuantity>=line.OrderedQuantity)) OR
              (po.Status='CANCELLED' AND line.CancelledQuantity<>line.OrderedQuantity) OR
              (po.Status IN ('OPEN','DELAYED','CANCELLED') AND line.ReceivedQuantity<>0))""",
            SOURCE,
        )
        status_count = fetch_scalar(
            connection,
            "SELECT COUNT(DISTINCT Status) FROM dbo.FactPurchaseOrder WHERE SourceSystem=?",
            SOURCE,
        )
    assert int(supplier_failures) == 0
    assert int(lifecycle_failures) == 0
    assert int(status_count) == 5
