"""Declarative SQL Server data-quality rules for analytical platform tables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationRule:
    """One count-based SQL validation with business metadata."""

    check_name: str
    table_name: str
    category: str
    severity: str
    records_sql: str
    failures_sql: str
    description: str


RULES: tuple[ValidationRule, ...] = (
    ValidationRule(
        "required_sales_fields",
        "FactSales",
        "COMPLETENESS",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactSales",
        """SELECT COUNT(*) FROM dbo.FactSales
        WHERE DateKey IS NULL OR ProductKey IS NULL OR StoreKey IS NULL OR Quantity IS NULL""",
        "Required sales keys and demand must be populated.",
    ),
    ValidationRule(
        "required_inventory_fields",
        "FactInventorySnapshot",
        "COMPLETENESS",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactInventorySnapshot",
        """SELECT COUNT(*) FROM dbo.FactInventorySnapshot
        WHERE DateKey IS NULL OR ProductKey IS NULL OR WarehouseKey IS NULL
           OR OpeningStock IS NULL OR ClosingStock IS NULL""",
        "Required inventory keys and balances must be populated.",
    ),
    ValidationRule(
        "duplicate_sales_business_grain",
        "FactSales",
        "UNIQUENESS",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactSales",
        """SELECT COALESCE(SUM(duplicate_count-1),0) FROM (
          SELECT COUNT_BIG(*) duplicate_count FROM dbo.FactSales
          GROUP BY DateKey,ProductKey,StoreKey HAVING COUNT_BIG(*)>1) duplicates""",
        "Sales must be unique by date, product, and store.",
    ),
    ValidationRule(
        "duplicate_inventory_business_grain",
        "FactInventorySnapshot",
        "UNIQUENESS",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactInventorySnapshot",
        """SELECT COALESCE(SUM(duplicate_count-1),0) FROM (
          SELECT COUNT_BIG(*) duplicate_count FROM dbo.FactInventorySnapshot
          GROUP BY DateKey,ProductKey,WarehouseKey HAVING COUNT_BIG(*)>1) duplicates""",
        "Inventory must be unique by date, product, and warehouse.",
    ),
    ValidationRule(
        "invalid_or_orphaned_fact_keys",
        "MultipleFacts",
        "REFERENTIAL_INTEGRITY",
        "CRITICAL",
        """SELECT (SELECT COUNT(*) FROM dbo.FactSales)
          +(SELECT COUNT(*) FROM dbo.FactInventorySnapshot)
          +(SELECT COUNT(*) FROM dbo.FactPurchaseOrder)""",
        """SELECT
          (SELECT COUNT(*) FROM dbo.FactSales f LEFT JOIN dbo.DimDate d ON d.DateKey=f.DateKey
            LEFT JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
            LEFT JOIN dbo.DimStore s ON s.StoreKey=f.StoreKey
            WHERE d.DateKey IS NULL OR p.ProductKey IS NULL OR s.StoreKey IS NULL)
          +(SELECT COUNT(*) FROM dbo.FactInventorySnapshot f
            LEFT JOIN dbo.DimDate d ON d.DateKey=f.DateKey
            LEFT JOIN dbo.DimProduct p ON p.ProductKey=f.ProductKey
            LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey=f.WarehouseKey
            WHERE d.DateKey IS NULL OR p.ProductKey IS NULL OR w.WarehouseKey IS NULL)
          +(SELECT COUNT(*) FROM dbo.FactPurchaseOrder f
            LEFT JOIN dbo.DimSupplier s ON s.SupplierKey=f.SupplierKey
            LEFT JOIN dbo.DimWarehouse w ON w.WarehouseKey=f.WarehouseKey
            WHERE s.SupplierKey IS NULL OR w.WarehouseKey IS NULL)""",
        "Loaded facts must resolve to valid dimension records.",
    ),
    ValidationRule(
        "invalid_dates",
        "DimDate",
        "VALIDITY",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.DimDate",
        """SELECT COUNT(*) FROM dbo.DimDate
        WHERE FullDate IS NULL OR DateKey<>YEAR(FullDate)*10000+MONTH(FullDate)*100+DAY(FullDate)
           OR MonthNumber NOT BETWEEN 1 AND 12 OR QuarterNumber NOT BETWEEN 1 AND 4""",
        "Date keys and calendar attributes must agree.",
    ),
    ValidationRule(
        "sales_date_range",
        "FactSales",
        "VALIDITY",
        "CRITICAL",
        """SELECT COUNT(*) FROM dbo.FactSales
        WHERE SourceSystem IN ('M5','SYNTHETIC_M5_SAMPLE')""",
        """SELECT COUNT(*) FROM dbo.FactSales f JOIN dbo.DimDate d ON d.DateKey=f.DateKey
        WHERE f.SourceSystem IN ('M5','SYNTHETIC_M5_SAMPLE')
          AND (d.FullDate<'2011-01-01' OR d.FullDate>'2030-12-31')""",
        "M5 and sample sales must remain within the documented supported range.",
    ),
    ValidationRule(
        "negative_sales_or_prices",
        "FactSales,FactSellPrice",
        "VALIDITY",
        "CRITICAL",
        "SELECT (SELECT COUNT(*) FROM dbo.FactSales)+(SELECT COUNT(*) FROM dbo.FactSellPrice)",
        """SELECT (SELECT COUNT(*) FROM dbo.FactSales WHERE Quantity<0 OR UnitPrice<0)
        +(SELECT COUNT(*) FROM dbo.FactSellPrice WHERE SellPrice<0)""",
        "Demand and monetary values cannot be negative.",
    ),
    ValidationRule(
        "inventory_closing_stock_reconciliation",
        "FactInventorySnapshot",
        "CONSISTENCY",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactInventorySnapshot",
        """SELECT COUNT(*) FROM dbo.FactInventorySnapshot
        WHERE ClosingStock<>OpeningStock+ReceivedQuantity-SoldQuantity-DamagedQuantity-
          ReservedQuantityAdjustment OR ClosingStock<0""",
        "Every daily inventory movement must reconcile exactly.",
    ),
    ValidationRule(
        "negative_forecasts",
        "FactForecast",
        "VALIDITY",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactForecast",
        "SELECT COUNT(*) FROM dbo.FactForecast WHERE ForecastQuantity<0 OR LowerBound<0",
        "Forecast demand and lower bounds cannot be negative.",
    ),
    ValidationRule(
        "supplier_capacity_below_minimum_order",
        "DimSupplier,BridgeSupplierProduct",
        "BUSINESS_RULE",
        "CRITICAL",
        """SELECT (SELECT COUNT(*) FROM dbo.DimSupplier)
          +(SELECT COUNT(*) FROM dbo.BridgeSupplierProduct)""",
        """SELECT (SELECT COUNT(*) FROM dbo.DimSupplier
          WHERE DailyCapacity<MinimumOrderQuantity OR MaximumOrderQuantity<MinimumOrderQuantity)
          +(SELECT COUNT(*) FROM dbo.BridgeSupplierProduct
          WHERE DailyCapacity<MinimumOrderQuantity OR MaximumOrderQuantity<MinimumOrderQuantity)""",
        "Supplier capacity and maximum quantities must support minimum orders.",
    ),
    ValidationRule(
        "warehouse_capacity_exceeded",
        "FactInventorySnapshot",
        "BUSINESS_RULE",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactInventorySnapshot",
        """SELECT COUNT(*) FROM (
          SELECT i.DateKey,i.WarehouseKey FROM dbo.FactInventorySnapshot i
          JOIN dbo.DimWarehouse w ON w.WarehouseKey=i.WarehouseKey
          GROUP BY i.DateKey,i.WarehouseKey
          HAVING SUM(i.ClosingStock)>MAX(w.CapacityUnits)) failures""",
        "Daily warehouse inventory must not exceed configured capacity.",
    ),
    ValidationRule(
        "purchase_order_lifecycle_consistency",
        "FactPurchaseOrder,FactPurchaseOrderLine",
        "CONSISTENCY",
        "CRITICAL",
        "SELECT COUNT(*) FROM dbo.FactPurchaseOrderLine",
        """SELECT COUNT(*) FROM dbo.FactPurchaseOrder po
        JOIN dbo.FactPurchaseOrderLine line ON line.PurchaseOrderKey=po.PurchaseOrderKey
        WHERE (po.Status='COMPLETED' AND line.ReceivedQuantity<>line.OrderedQuantity)
           OR (po.Status='PARTIAL' AND
             (line.ReceivedQuantity<=0 OR line.ReceivedQuantity>=line.OrderedQuantity))
           OR (po.Status='CANCELLED' AND line.CancelledQuantity<>line.OrderedQuantity)
           OR (po.Status IN ('OPEN','DELAYED','CANCELLED') AND line.ReceivedQuantity<>0)""",
        "Order status must agree with received and cancelled quantities.",
    ),
)
