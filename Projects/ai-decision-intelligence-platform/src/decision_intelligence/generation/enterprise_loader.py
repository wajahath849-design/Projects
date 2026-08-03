"""Transactional SQL Server upserts for generated enterprise operations."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import pyodbc

from decision_intelligence.database.initializer import execute_script
from decision_intelligence.generation.enterprise_generator import EnterpriseData
from decision_intelligence.ingestion.database_loader import _stage_rows


def _records(frame: pd.DataFrame, columns: list[str]) -> list[tuple[Any, ...]]:
    return [
        tuple(None if pd.isna(value) else value for value in row)
        for row in frame[columns].itertuples(index=False, name=None)
    ]


def apply_enterprise_migration(connection: pyodbc.Connection, path: Path) -> None:
    """Apply the documented Phase 3 support-table migration."""
    execute_script(connection, path)


def load_enterprise_data(
    connection: pyodbc.Connection,
    data: EnterpriseData,
    pipeline_run_id: uuid.UUID,
    batch_size: int = 2000,
) -> None:
    """Upsert the complete generated dataset within the caller's transaction."""
    source = "SYNTHETIC_ENTERPRISE"
    version = "phase-3-v1"
    suppliers = [
        row + (source, version) for row in _records(data.suppliers, list(data.suppliers.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #SupplierStage; CREATE TABLE #SupplierStage(
      SupplierID nvarchar(50),SupplierName nvarchar(150),SupplierRegion nvarchar(100),
      ReliabilityScore decimal(9,6),BaseLeadTimeDays smallint,LeadTimeVariability decimal(9,4),
      DelayProbability decimal(9,6),MinimumOrderQuantity decimal(19,4),MaximumOrderQuantity decimal(19,4),
      DailyCapacity decimal(19,4),PaymentTermsDays smallint,RiskLevel nvarchar(20),ActiveFlag bit,
      SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #SupplierStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        """
      MERGE dbo.DimSupplier t USING #SupplierStage s ON t.SupplierID=s.SupplierID
      WHEN MATCHED THEN UPDATE SET SupplierName=s.SupplierName,SupplierRegion=s.SupplierRegion,
      ReliabilityScore=s.ReliabilityScore,BaseLeadTimeDays=s.BaseLeadTimeDays,
      LeadTimeVariability=s.LeadTimeVariability,DelayProbability=s.DelayProbability,
      MinimumOrderQuantity=s.MinimumOrderQuantity,MaximumOrderQuantity=s.MaximumOrderQuantity,
      DailyCapacity=s.DailyCapacity,PaymentTermsDays=s.PaymentTermsDays,RiskLevel=s.RiskLevel,
      ActiveFlag=s.ActiveFlag,UpdatedAt=SYSUTCDATETIME(),SourceSystem=s.SourceSystem,DataVersion=s.DataVersion
      WHEN NOT MATCHED THEN INSERT (SupplierID,SupplierName,SupplierRegion,ReliabilityScore,
      BaseLeadTimeDays,LeadTimeVariability,DelayProbability,MinimumOrderQuantity,MaximumOrderQuantity,
      DailyCapacity,PaymentTermsDays,RiskLevel,ActiveFlag,SourceSystem,DataVersion) VALUES
      (s.SupplierID,s.SupplierName,s.SupplierRegion,s.ReliabilityScore,s.BaseLeadTimeDays,
      s.LeadTimeVariability,s.DelayProbability,s.MinimumOrderQuantity,s.MaximumOrderQuantity,
      s.DailyCapacity,s.PaymentTermsDays,s.RiskLevel,s.ActiveFlag,s.SourceSystem,s.DataVersion);""",
        suppliers,
        batch_size,
    )

    warehouses = [
        row + (source, version) for row in _records(data.warehouses, list(data.warehouses.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #WarehouseStage; CREATE TABLE #WarehouseStage(
      WarehouseID nvarchar(50),WarehouseName nvarchar(100),StateID nvarchar(20),CapacityUnits decimal(19,4),
      CurrentUtilization decimal(9,6),HoldingCostPerUnitDay decimal(19,6),HandlingCostPerUnit decimal(19,4),
      ServiceLevelTarget decimal(9,6),ActiveFlag bit,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #WarehouseStage VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.DimWarehouse t USING (
      SELECT s.*,d.StateKey FROM #WarehouseStage s JOIN dbo.DimState d ON d.StateID=s.StateID) x
      ON t.WarehouseID=x.WarehouseID WHEN MATCHED THEN UPDATE SET WarehouseName=x.WarehouseName,
      StateKey=x.StateKey,CapacityUnits=x.CapacityUnits,CurrentUtilization=x.CurrentUtilization,
      HoldingCostPerUnitDay=x.HoldingCostPerUnitDay,HandlingCostPerUnit=x.HandlingCostPerUnit,
      ServiceLevelTarget=x.ServiceLevelTarget,ActiveFlag=x.ActiveFlag,UpdatedAt=SYSUTCDATETIME(),
      SourceSystem=x.SourceSystem,DataVersion=x.DataVersion WHEN NOT MATCHED THEN INSERT
      (WarehouseID,WarehouseName,StateKey,CapacityUnits,CurrentUtilization,HoldingCostPerUnitDay,
      HandlingCostPerUnit,ServiceLevelTarget,ActiveFlag,SourceSystem,DataVersion) VALUES
      (x.WarehouseID,x.WarehouseName,x.StateKey,x.CapacityUnits,x.CurrentUtilization,
      x.HoldingCostPerUnitDay,x.HandlingCostPerUnit,x.ServiceLevelTarget,x.ActiveFlag,x.SourceSystem,x.DataVersion);""",
        warehouses,
        batch_size,
    )

    relationships = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.supplier_products, list(data.supplier_products.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #SupplierProductStage; CREATE TABLE #SupplierProductStage(
      SupplierID nvarchar(50),ProductID nvarchar(100),PurchaseCost decimal(19,4),MinimumOrderQuantity decimal(19,4),
      MaximumOrderQuantity decimal(19,4),DailyCapacity decimal(19,4),LeadTimeDays smallint,
      PreferredSupplierFlag bit,ActiveFlag bit,PipelineRunID uniqueidentifier,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #SupplierProductStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.BridgeSupplierProduct t USING (
      SELECT s.*,ds.SupplierKey,p.ProductKey FROM #SupplierProductStage s
      JOIN dbo.DimSupplier ds ON ds.SupplierID=s.SupplierID JOIN dbo.DimProduct p ON p.ProductID=s.ProductID) x
      ON t.SupplierKey=x.SupplierKey AND t.ProductKey=x.ProductKey WHEN MATCHED THEN UPDATE SET
      PurchaseCost=x.PurchaseCost,MinimumOrderQuantity=x.MinimumOrderQuantity,MaximumOrderQuantity=x.MaximumOrderQuantity,
      DailyCapacity=x.DailyCapacity,LeadTimeDays=x.LeadTimeDays,PreferredSupplierFlag=x.PreferredSupplierFlag,
      ActiveFlag=x.ActiveFlag,UpdatedAt=SYSUTCDATETIME(),PipelineRunID=x.PipelineRunID,SourceSystem=x.SourceSystem,
      DataVersion=x.DataVersion WHEN NOT MATCHED THEN INSERT (SupplierKey,ProductKey,PurchaseCost,
      MinimumOrderQuantity,MaximumOrderQuantity,DailyCapacity,LeadTimeDays,PreferredSupplierFlag,ActiveFlag,
      PipelineRunID,SourceSystem,DataVersion) VALUES (x.SupplierKey,x.ProductKey,x.PurchaseCost,x.MinimumOrderQuantity,
      x.MaximumOrderQuantity,x.DailyCapacity,x.LeadTimeDays,x.PreferredSupplierFlag,x.ActiveFlag,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        relationships,
        batch_size,
    )

    lanes = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.transportation_lanes, list(data.transportation_lanes.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #LaneStage; CREATE TABLE #LaneStage(
      SupplierID nvarchar(50),WarehouseID nvarchar(50),DistanceKM decimal(19,4),BaseShippingCost decimal(19,4),
      ShippingCostPerUnit decimal(19,6),AverageTransitDays decimal(9,4),TransitVariability decimal(9,4),
      CarbonEmissionPerUnit decimal(19,6),PreferredLaneFlag bit,PipelineRunID uniqueidentifier,
      SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #LaneStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        """
      MERGE dbo.FactTransportation t USING (SELECT s.*,ds.SupplierKey,w.WarehouseKey FROM #LaneStage s
      JOIN dbo.DimSupplier ds ON ds.SupplierID=s.SupplierID JOIN dbo.DimWarehouse w ON w.WarehouseID=s.WarehouseID) x
      ON t.SupplierKey=x.SupplierKey AND t.WarehouseKey=x.WarehouseKey WHEN MATCHED THEN UPDATE SET
      DistanceKM=x.DistanceKM,BaseShippingCost=x.BaseShippingCost,ShippingCostPerUnit=x.ShippingCostPerUnit,
      AverageTransitDays=x.AverageTransitDays,TransitVariability=x.TransitVariability,
      CarbonEmissionPerUnit=x.CarbonEmissionPerUnit,PreferredLaneFlag=x.PreferredLaneFlag,
      UpdatedAt=SYSUTCDATETIME(),PipelineRunID=x.PipelineRunID,SourceSystem=x.SourceSystem,DataVersion=x.DataVersion
      WHEN NOT MATCHED THEN INSERT (SupplierKey,WarehouseKey,DistanceKM,BaseShippingCost,ShippingCostPerUnit,
      AverageTransitDays,TransitVariability,CarbonEmissionPerUnit,PreferredLaneFlag,PipelineRunID,SourceSystem,DataVersion)
      VALUES (x.SupplierKey,x.WarehouseKey,x.DistanceKM,x.BaseShippingCost,x.ShippingCostPerUnit,
      x.AverageTransitDays,x.TransitVariability,x.CarbonEmissionPerUnit,x.PreferredLaneFlag,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        lanes,
        batch_size,
    )

    orders = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.purchase_orders, list(data.purchase_orders.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #POStage; CREATE TABLE #POStage(
      PurchaseOrderID nvarchar(50),SupplierID nvarchar(50),WarehouseID nvarchar(50),OrderDateKey int,
      ExpectedDeliveryDateKey int,ActualDeliveryDateKey int NULL,Status nvarchar(20),
      TotalPurchaseCost decimal(19,4),TotalTransportationCost decimal(19,4),PipelineRunID uniqueidentifier,
      SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #POStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        """
      MERGE dbo.FactPurchaseOrder t USING (SELECT s.*,ds.SupplierKey,w.WarehouseKey FROM #POStage s
      JOIN dbo.DimSupplier ds ON ds.SupplierID=s.SupplierID JOIN dbo.DimWarehouse w ON w.WarehouseID=s.WarehouseID) x
      ON t.PurchaseOrderID=x.PurchaseOrderID WHEN MATCHED THEN UPDATE SET SupplierKey=x.SupplierKey,
      WarehouseKey=x.WarehouseKey,OrderDateKey=x.OrderDateKey,ExpectedDeliveryDateKey=x.ExpectedDeliveryDateKey,
      ActualDeliveryDateKey=x.ActualDeliveryDateKey,Status=x.Status,TotalPurchaseCost=x.TotalPurchaseCost,
      TotalTransportationCost=x.TotalTransportationCost,UpdatedAt=SYSUTCDATETIME(),PipelineRunID=x.PipelineRunID,
      SourceSystem=x.SourceSystem,DataVersion=x.DataVersion WHEN NOT MATCHED THEN INSERT
      (PurchaseOrderID,SupplierKey,WarehouseKey,OrderDateKey,ExpectedDeliveryDateKey,ActualDeliveryDateKey,
      Status,TotalPurchaseCost,TotalTransportationCost,PipelineRunID,SourceSystem,DataVersion) VALUES
      (x.PurchaseOrderID,x.SupplierKey,x.WarehouseKey,x.OrderDateKey,x.ExpectedDeliveryDateKey,
      x.ActualDeliveryDateKey,x.Status,x.TotalPurchaseCost,x.TotalTransportationCost,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        orders,
        batch_size,
    )

    lines = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.purchase_order_lines, list(data.purchase_order_lines.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #POLineStage; CREATE TABLE #POLineStage(
      PurchaseOrderID nvarchar(50),LineNumber int,ProductID nvarchar(100),OrderedQuantity decimal(19,4),
      ReceivedQuantity decimal(19,4),CancelledQuantity decimal(19,4),UnitCost decimal(19,4),
      PipelineRunID uniqueidentifier,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #POLineStage VALUES (?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.FactPurchaseOrderLine t USING (
      SELECT s.*,po.PurchaseOrderKey,p.ProductKey FROM #POLineStage s
      JOIN dbo.FactPurchaseOrder po ON po.PurchaseOrderID=s.PurchaseOrderID
      JOIN dbo.DimProduct p ON p.ProductID=s.ProductID) x
      ON t.PurchaseOrderKey=x.PurchaseOrderKey AND t.LineNumber=x.LineNumber WHEN MATCHED THEN UPDATE SET
      ProductKey=x.ProductKey,OrderedQuantity=x.OrderedQuantity,ReceivedQuantity=x.ReceivedQuantity,
      CancelledQuantity=x.CancelledQuantity,UnitCost=x.UnitCost,UpdatedAt=SYSUTCDATETIME(),
      PipelineRunID=x.PipelineRunID,SourceSystem=x.SourceSystem,DataVersion=x.DataVersion WHEN NOT MATCHED THEN INSERT
      (PurchaseOrderKey,LineNumber,ProductKey,OrderedQuantity,ReceivedQuantity,CancelledQuantity,UnitCost,
      PipelineRunID,SourceSystem,DataVersion) VALUES (x.PurchaseOrderKey,x.LineNumber,x.ProductKey,
      x.OrderedQuantity,x.ReceivedQuantity,x.CancelledQuantity,x.UnitCost,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        lines,
        batch_size,
    )

    inventory = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.inventory_snapshots, list(data.inventory_snapshots.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #InventoryStage; CREATE TABLE #InventoryStage(
      DateKey int,ProductID nvarchar(100),WarehouseID nvarchar(50),OpeningStock decimal(19,4),
      ReceivedQuantity decimal(19,4),SoldQuantity decimal(19,4),DamagedQuantity decimal(19,4),
      ReservedQuantityAdjustment decimal(19,4),ClosingStock decimal(19,4),LostSalesQuantity decimal(19,4),
      InventoryValue decimal(19,4),PipelineRunID uniqueidentifier,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #InventoryStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.FactInventorySnapshot t USING (
      SELECT s.*,p.ProductKey,w.WarehouseKey FROM #InventoryStage s JOIN dbo.DimProduct p ON p.ProductID=s.ProductID
      JOIN dbo.DimWarehouse w ON w.WarehouseID=s.WarehouseID) x ON t.DateKey=x.DateKey
      AND t.ProductKey=x.ProductKey AND t.WarehouseKey=x.WarehouseKey WHEN MATCHED THEN UPDATE SET
      OpeningStock=x.OpeningStock,ReceivedQuantity=x.ReceivedQuantity,SoldQuantity=x.SoldQuantity,
      DamagedQuantity=x.DamagedQuantity,ReservedQuantityAdjustment=x.ReservedQuantityAdjustment,
      ClosingStock=x.ClosingStock,LostSalesQuantity=x.LostSalesQuantity,InventoryValue=x.InventoryValue,
      UpdatedAt=SYSUTCDATETIME(),PipelineRunID=x.PipelineRunID,SourceSystem=x.SourceSystem,DataVersion=x.DataVersion
      WHEN NOT MATCHED THEN INSERT (DateKey,ProductKey,WarehouseKey,OpeningStock,ReceivedQuantity,SoldQuantity,
      DamagedQuantity,ReservedQuantityAdjustment,ClosingStock,LostSalesQuantity,InventoryValue,
      PipelineRunID,SourceSystem,DataVersion) VALUES (x.DateKey,x.ProductKey,x.WarehouseKey,x.OpeningStock,
      x.ReceivedQuantity,x.SoldQuantity,x.DamagedQuantity,x.ReservedQuantityAdjustment,x.ClosingStock,
      x.LostSalesQuantity,x.InventoryValue,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        inventory,
        batch_size,
    )

    constraints = [
        row + (pipeline_run_id, source, version)
        for row in _records(data.business_constraints, list(data.business_constraints.columns))
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #ConstraintStage; CREATE TABLE #ConstraintStage(
      ConstraintID nvarchar(100),ConstraintType nvarchar(50),ScopeType nvarchar(30),ScopeID nvarchar(100) NULL,
      ParameterName nvarchar(100),ParameterValue decimal(19,6),UnitOfMeasure nvarchar(30),EffectiveDateKey int,
      ExpirationDateKey int NULL,ActiveFlag bit,PipelineRunID uniqueidentifier,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #ConstraintStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.BusinessConstraint t
      USING #ConstraintStage x ON t.ConstraintID=x.ConstraintID WHEN MATCHED THEN UPDATE SET
      ConstraintType=x.ConstraintType,ScopeType=x.ScopeType,ScopeID=x.ScopeID,ParameterName=x.ParameterName,
      ParameterValue=x.ParameterValue,UnitOfMeasure=x.UnitOfMeasure,EffectiveDateKey=x.EffectiveDateKey,
      ExpirationDateKey=x.ExpirationDateKey,ActiveFlag=x.ActiveFlag,UpdatedAt=SYSUTCDATETIME(),
      PipelineRunID=x.PipelineRunID,SourceSystem=x.SourceSystem,DataVersion=x.DataVersion WHEN NOT MATCHED THEN INSERT
      (ConstraintID,ConstraintType,ScopeType,ScopeID,ParameterName,ParameterValue,UnitOfMeasure,
      EffectiveDateKey,ExpirationDateKey,ActiveFlag,PipelineRunID,SourceSystem,DataVersion) VALUES
      (x.ConstraintID,x.ConstraintType,x.ScopeType,x.ScopeID,x.ParameterName,x.ParameterValue,x.UnitOfMeasure,
      x.EffectiveDateKey,x.ExpirationDateKey,x.ActiveFlag,x.PipelineRunID,x.SourceSystem,x.DataVersion);""",
        constraints,
        batch_size,
    )
