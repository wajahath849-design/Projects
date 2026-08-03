"""Chunk-safe SQL Server upserts for validated M5 records."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

import pandas as pd
import pyodbc

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadContext:
    """Audit values applied consistently to one ingestion run."""

    pipeline_run_id: uuid.UUID
    source_system: str
    data_version: str
    batch_size: int


def _batched(rows: Sequence[tuple[Any, ...]], size: int) -> Iterable[Sequence[tuple[Any, ...]]]:
    if size <= 0:
        raise ValueError("Database batch size must be positive")
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _stage_rows(
    connection: pyodbc.Connection,
    create_sql: str,
    insert_sql: str,
    merge_sql: str,
    rows: Sequence[tuple[Any, ...]],
    batch_size: int,
) -> None:
    if not rows:
        return
    cursor = connection.cursor()
    cursor.execute(create_sql)
    for batch in _batched(rows, batch_size):
        if any(value is None for row in batch for value in row):
            for row in batch:
                cursor.execute(insert_sql, row)
            continue
        # Small batches use regular executemany because some Windows ODBC builds
        # can leave asynchronous temp-table inserts active after process exit.
        # Full-data batches still use the driver's bulk array-binding path.
        cursor.fast_executemany = len(batch) >= 1000
        cursor.executemany(insert_sql, batch)
    cursor.fast_executemany = False
    cursor.execute(merge_sql)
    while cursor.nextset():
        pass


def upsert_calendar(
    connection: pyodbc.Connection,
    calendar: pd.DataFrame,
    context: LoadContext,
) -> None:
    """Upsert M5 calendar records into DimDate."""
    rows: list[tuple[Any, ...]] = []
    for row in calendar.itertuples(index=False):
        timestamp = pd.Timestamp(cast(Any, row.date))
        month = int(str(row.month))
        rows.append(
            (
                int(timestamp.strftime("%Y%m%d")),
                timestamp.date(),
                int(str(row.wday)),
                str(row.weekday),
                int(timestamp.isocalendar().week),
                month,
                timestamp.strftime("%B"),
                int((month - 1) // 3 + 1),
                int(str(row.year)),
                int(timestamp.weekday() >= 5),
                None if pd.isna(row.event_name_1) else str(row.event_name_1),
                None if pd.isna(row.event_type_1) else str(row.event_type_1),
                int(str(row.snap_CA)),
                int(str(row.snap_TX)),
                int(str(row.snap_WI)),
                context.source_system,
                context.data_version,
            )
        )
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #CalendarStage;
        CREATE TABLE #CalendarStage (
            DateKey int, FullDate date, DayOfWeek tinyint, DayName nvarchar(10),
            WeekOfYear tinyint, MonthNumber tinyint, MonthName nvarchar(10), QuarterNumber tinyint,
            CalendarYear smallint, IsWeekend bit, EventName nvarchar(100) NULL,
            EventType nvarchar(50) NULL, SnapCA bit, SnapTX bit, SnapWI bit,
            SourceSystem nvarchar(50), DataVersion nvarchar(50)
        )""",
        "INSERT #CalendarStage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        """MERGE dbo.DimDate AS target USING #CalendarStage AS source
        ON target.DateKey=source.DateKey
        WHEN MATCHED THEN UPDATE SET FullDate=source.FullDate, DayOfWeek=source.DayOfWeek,
          DayName=source.DayName, WeekOfYear=source.WeekOfYear, MonthNumber=source.MonthNumber,
          MonthName=source.MonthName, QuarterNumber=source.QuarterNumber,
          CalendarYear=source.CalendarYear, IsWeekend=source.IsWeekend,
          EventName=source.EventName, EventType=source.EventType, SnapCA=source.SnapCA,
          SnapTX=source.SnapTX, SnapWI=source.SnapWI, UpdatedAt=SYSUTCDATETIME(),
          SourceSystem=source.SourceSystem, DataVersion=source.DataVersion
        WHEN NOT MATCHED THEN INSERT (DateKey,FullDate,DayOfWeek,DayName,WeekOfYear,
          MonthNumber,MonthName,QuarterNumber,CalendarYear,IsWeekend,EventName,EventType,
          SnapCA,SnapTX,SnapWI,SourceSystem,DataVersion)
          VALUES (source.DateKey,source.FullDate,source.DayOfWeek,source.DayName,source.WeekOfYear,
          source.MonthNumber,source.MonthName,source.QuarterNumber,source.CalendarYear,
          source.IsWeekend,source.EventName,source.EventType,source.SnapCA,source.SnapTX,
          source.SnapWI,source.SourceSystem,source.DataVersion);""",
        rows,
        context.batch_size,
    )


def upsert_sales_dimensions(
    connection: pyodbc.Connection,
    metadata: pd.DataFrame,
    context: LoadContext,
) -> None:
    """Upsert states, departments, products, and stores from sales metadata."""
    unique = metadata[["item_id", "dept_id", "cat_id", "store_id", "state_id"]].drop_duplicates()
    rows = [
        tuple(map(str, row)) + (context.source_system, context.data_version)
        for row in unique.itertuples(index=False, name=None)
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #MetadataStage;
        CREATE TABLE #MetadataStage (
          ItemID nvarchar(100), DepartmentID nvarchar(50), CategoryID nvarchar(50),
          StoreID nvarchar(50), StateID nvarchar(20), SourceSystem nvarchar(50), DataVersion nvarchar(50)
        )""",
        "INSERT #MetadataStage VALUES (?,?,?,?,?,?,?)",
        """MERGE dbo.DimState AS target USING (SELECT DISTINCT StateID FROM #MetadataStage) source
          ON target.StateID=source.StateID WHEN NOT MATCHED THEN
          INSERT (StateID,StateName,SourceSystem) VALUES (source.StateID,source.StateID,(SELECT TOP 1 SourceSystem FROM #MetadataStage));
        MERGE dbo.DimCategory AS target USING (SELECT DISTINCT DepartmentID,CategoryID FROM #MetadataStage) source
          ON target.CategoryID=source.DepartmentID WHEN NOT MATCHED THEN
          INSERT (CategoryID,CategoryName,DepartmentID,DepartmentName,SourceSystem,DataVersion)
          VALUES (source.DepartmentID,source.CategoryID,source.DepartmentID,source.DepartmentID,
          (SELECT TOP 1 SourceSystem FROM #MetadataStage),(SELECT TOP 1 DataVersion FROM #MetadataStage));
        MERGE dbo.DimProduct AS target USING (
          SELECT DISTINCT m.ItemID,m.DepartmentID,m.SourceSystem,m.DataVersion,c.CategoryKey
          FROM #MetadataStage m JOIN dbo.DimCategory c ON c.CategoryID=m.DepartmentID) source
          ON target.ProductID=source.ItemID WHEN NOT MATCHED THEN
          INSERT (ProductID,ItemID,CategoryKey,ProductName,SourceSystem,DataVersion)
          VALUES (source.ItemID,source.ItemID,source.CategoryKey,source.ItemID,source.SourceSystem,source.DataVersion);
        MERGE dbo.DimStore AS target USING (
          SELECT DISTINCT m.StoreID,m.SourceSystem,m.DataVersion,s.StateKey
          FROM #MetadataStage m JOIN dbo.DimState s ON s.StateID=m.StateID) source
          ON target.StoreID=source.StoreID WHEN NOT MATCHED THEN
          INSERT (StoreID,StoreName,StateKey,SourceSystem,DataVersion)
          VALUES (source.StoreID,source.StoreID,source.StateKey,source.SourceSystem,source.DataVersion);""",
        rows,
        context.batch_size,
    )


def upsert_sales(
    connection: pyodbc.Connection,
    rows: Sequence[tuple[int, str, str, float]],
    context: LoadContext,
) -> None:
    """Upsert long-form daily demand into FactSales."""
    audited = [
        row + (context.pipeline_run_id, context.source_system, context.data_version) for row in rows
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #SalesStage;
        CREATE TABLE #SalesStage (DateKey int,ProductID nvarchar(100),StoreID nvarchar(50),
          Quantity decimal(19,4),PipelineRunID uniqueidentifier,SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #SalesStage VALUES (?,?,?,?,?,?,?)",
        """MERGE dbo.FactSales AS target USING (
          SELECT s.DateKey,p.ProductKey,st.StoreKey,s.Quantity,s.PipelineRunID,s.SourceSystem,s.DataVersion
          FROM #SalesStage s JOIN dbo.DimProduct p ON p.ProductID=s.ProductID
          JOIN dbo.DimStore st ON st.StoreID=s.StoreID) source
        ON target.DateKey=source.DateKey AND target.ProductKey=source.ProductKey AND target.StoreKey=source.StoreKey
        WHEN MATCHED THEN UPDATE SET Quantity=source.Quantity,UpdatedAt=SYSUTCDATETIME(),
          PipelineRunID=source.PipelineRunID,SourceSystem=source.SourceSystem,DataVersion=source.DataVersion
        WHEN NOT MATCHED THEN INSERT (DateKey,ProductKey,StoreKey,Quantity,PipelineRunID,SourceSystem,DataVersion)
          VALUES (source.DateKey,source.ProductKey,source.StoreKey,source.Quantity,
          source.PipelineRunID,source.SourceSystem,source.DataVersion);""",
        audited,
        context.batch_size,
    )


def upsert_prices(
    connection: pyodbc.Connection,
    rows: Sequence[tuple[int, str, str, str, float]],
    context: LoadContext,
) -> None:
    """Expand and upsert weekly prices at the daily analytical grain."""
    audited = [
        row + (context.pipeline_run_id, context.source_system, context.data_version) for row in rows
    ]
    _stage_rows(
        connection,
        """DROP TABLE IF EXISTS #PriceStage;
        CREATE TABLE #PriceStage (DateKey int,ProductID nvarchar(100),StoreID nvarchar(50),
          WeekIdentifier nvarchar(20),SellPrice decimal(19,4),PipelineRunID uniqueidentifier,
          SourceSystem nvarchar(50),DataVersion nvarchar(50))""",
        "INSERT #PriceStage VALUES (?,?,?,?,?,?,?,?)",
        """MERGE dbo.FactSellPrice AS target USING (
          SELECT s.DateKey,p.ProductKey,st.StoreKey,s.WeekIdentifier,s.SellPrice,
          s.PipelineRunID,s.SourceSystem,s.DataVersion FROM #PriceStage s
          JOIN dbo.DimProduct p ON p.ProductID=s.ProductID
          JOIN dbo.DimStore st ON st.StoreID=s.StoreID) source
        ON target.DateKey=source.DateKey AND target.ProductKey=source.ProductKey AND target.StoreKey=source.StoreKey
        WHEN MATCHED THEN UPDATE SET WeekIdentifier=source.WeekIdentifier,SellPrice=source.SellPrice,
          UpdatedAt=SYSUTCDATETIME(),PipelineRunID=source.PipelineRunID,
          SourceSystem=source.SourceSystem,DataVersion=source.DataVersion
        WHEN NOT MATCHED THEN INSERT (DateKey,ProductKey,StoreKey,WeekIdentifier,SellPrice,
          PipelineRunID,SourceSystem,DataVersion) VALUES (source.DateKey,source.ProductKey,
          source.StoreKey,source.WeekIdentifier,source.SellPrice,source.PipelineRunID,
          source.SourceSystem,source.DataVersion);""",
        audited,
        context.batch_size,
    )
