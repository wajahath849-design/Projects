from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session


class IngestionError(ValueError):
    pass


def _read_csv(file_path: str | Path) -> pd.DataFrame:
    path = Path(file_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise IngestionError(f"CSV file not found: {path}")
    if path.suffix.lower() != ".csv":
        raise IngestionError("Only CSV files are accepted by this ingestion function")
    return pd.read_csv(path)


def _require_columns(data: pd.DataFrame, required: set[str]) -> None:
    missing = required.difference(data.columns)
    if missing:
        raise IngestionError(f"Missing columns: {sorted(missing)}")


def _dimension_map(session: Session, table_name: str, code_column: str, id_column: str) -> dict[str, int]:
    allowed = {
        ("inventory.dim_warehouse", "warehouse_code", "warehouse_id"),
        ("inventory.dim_sku", "sku_code", "sku_id"),
        ("inventory.dim_supplier", "supplier_code", "supplier_id"),
    }
    if (table_name, code_column, id_column) not in allowed:
        raise IngestionError("Unsupported dimension mapping")
    rows = session.execute(text(f"SELECT {code_column}, {id_column} FROM {table_name}")).all()
    return {str(code): int(identifier) for code, identifier in rows}


def _map_codes(data: pd.DataFrame, column: str, mapping: dict[str, int], target_column: str) -> pd.DataFrame:
    data = data.copy()
    data[column] = data[column].astype(str).str.strip().str.upper()
    data[target_column] = data[column].map(mapping)
    unknown = sorted(data.loc[data[target_column].isna(), column].unique().tolist())
    if unknown:
        raise IngestionError(f"Unknown values in {column}: {unknown[:20]}")
    data[target_column] = data[target_column].astype(int)
    return data


def ingest_transactions(session: Session, file_path: str | Path) -> int:
    data = _read_csv(file_path)
    _require_columns(
        data,
        {
            "source_transaction_id",
            "transaction_ts",
            "warehouse_code",
            "sku_code",
            "transaction_type",
            "quantity",
        },
    )
    warehouse_map = _dimension_map(session, "inventory.dim_warehouse", "warehouse_code", "warehouse_id")
    sku_map = _dimension_map(session, "inventory.dim_sku", "sku_code", "sku_id")
    data = _map_codes(data, "warehouse_code", warehouse_map, "warehouse_id")
    data = _map_codes(data, "sku_code", sku_map, "sku_id")

    data["transaction_ts"] = pd.to_datetime(data["transaction_ts"], utc=True, errors="raise")
    data["transaction_type"] = data["transaction_type"].astype(str).str.strip().str.upper()
    allowed_types = {"SALE", "RECEIPT", "ADJUSTMENT", "TRANSFER_IN", "TRANSFER_OUT", "RETURN", "DAMAGE"}
    invalid_types = sorted(set(data["transaction_type"]) - allowed_types)
    if invalid_types:
        raise IngestionError(f"Invalid transaction_type values: {invalid_types}")
    data["quantity"] = pd.to_numeric(data["quantity"], errors="raise")
    if "unit_cost" not in data:
        data["unit_cost"] = None
    else:
        data["unit_cost"] = pd.to_numeric(data["unit_cost"], errors="coerce")
    if "source_system" not in data:
        data["source_system"] = "CSV"

    statement = text(
        """
        INSERT INTO inventory.inventory_transactions
            (source_transaction_id, transaction_ts, warehouse_id, sku_id, transaction_type,
             quantity, unit_cost, source_system)
        VALUES
            (:source_transaction_id, :transaction_ts, :warehouse_id, :sku_id, :transaction_type,
             :quantity, :unit_cost, :source_system)
        ON CONFLICT (source_system, source_transaction_id) DO UPDATE SET
            transaction_ts = EXCLUDED.transaction_ts,
            warehouse_id = EXCLUDED.warehouse_id,
            sku_id = EXCLUDED.sku_id,
            transaction_type = EXCLUDED.transaction_type,
            quantity = EXCLUDED.quantity,
            unit_cost = EXCLUDED.unit_cost,
            ingested_at = CURRENT_TIMESTAMP
        """
    )
    records = data[
        [
            "source_transaction_id",
            "transaction_ts",
            "warehouse_id",
            "sku_id",
            "transaction_type",
            "quantity",
            "unit_cost",
            "source_system",
        ]
    ].to_dict("records")
    session.execute(statement, records)
    return len(records)


def ingest_snapshots(session: Session, file_path: str | Path) -> int:
    data = _read_csv(file_path)
    _require_columns(data, {"snapshot_ts", "warehouse_code", "sku_code", "on_hand_qty"})
    warehouse_map = _dimension_map(session, "inventory.dim_warehouse", "warehouse_code", "warehouse_id")
    sku_map = _dimension_map(session, "inventory.dim_sku", "sku_code", "sku_id")
    data = _map_codes(data, "warehouse_code", warehouse_map, "warehouse_id")
    data = _map_codes(data, "sku_code", sku_map, "sku_id")
    data["snapshot_ts"] = pd.to_datetime(data["snapshot_ts"], utc=True, errors="raise")
    for column in ("on_hand_qty", "allocated_qty", "on_order_qty", "backorder_qty"):
        if column not in data:
            data[column] = 0.0
        data[column] = pd.to_numeric(data[column], errors="raise")
        if (data[column] < 0).any():
            raise IngestionError(f"{column} cannot contain negative values")
    if "source_system" not in data:
        data["source_system"] = "CSV"

    statement = text(
        """
        INSERT INTO inventory.inventory_snapshots
            (snapshot_ts, warehouse_id, sku_id, on_hand_qty, allocated_qty, on_order_qty,
             backorder_qty, source_system)
        VALUES
            (:snapshot_ts, :warehouse_id, :sku_id, :on_hand_qty, :allocated_qty, :on_order_qty,
             :backorder_qty, :source_system)
        ON CONFLICT (snapshot_ts, warehouse_id, sku_id) DO UPDATE SET
            on_hand_qty = EXCLUDED.on_hand_qty,
            allocated_qty = EXCLUDED.allocated_qty,
            on_order_qty = EXCLUDED.on_order_qty,
            backorder_qty = EXCLUDED.backorder_qty,
            source_system = EXCLUDED.source_system,
            ingested_at = CURRENT_TIMESTAMP
        """
    )
    records = data[
        [
            "snapshot_ts",
            "warehouse_id",
            "sku_id",
            "on_hand_qty",
            "allocated_qty",
            "on_order_qty",
            "backorder_qty",
            "source_system",
        ]
    ].to_dict("records")
    session.execute(statement, records)
    return len(records)


def ingest_lead_times(session: Session, file_path: str | Path) -> int:
    data = _read_csv(file_path)
    _require_columns(data, {"supplier_code", "warehouse_code", "sku_code", "purchase_order_no", "order_date"})
    supplier_map = _dimension_map(session, "inventory.dim_supplier", "supplier_code", "supplier_id")
    warehouse_map = _dimension_map(session, "inventory.dim_warehouse", "warehouse_code", "warehouse_id")
    sku_map = _dimension_map(session, "inventory.dim_sku", "sku_code", "sku_id")
    data = _map_codes(data, "supplier_code", supplier_map, "supplier_id")
    data = _map_codes(data, "warehouse_code", warehouse_map, "warehouse_id")
    data = _map_codes(data, "sku_code", sku_map, "sku_id")

    for column in ("order_date", "promised_date", "receipt_date"):
        if column not in data:
            data[column] = None
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.date
    if data["order_date"].isna().any():
        raise IngestionError("order_date contains invalid dates")
    if "delay_reason" not in data:
        data["delay_reason"] = None

    statement = text(
        """
        INSERT INTO inventory.supplier_lead_time_events
            (supplier_id, warehouse_id, sku_id, purchase_order_no, promised_date,
             order_date, receipt_date, delay_reason)
        VALUES
            (:supplier_id, :warehouse_id, :sku_id, :purchase_order_no, :promised_date,
             :order_date, :receipt_date, :delay_reason)
        ON CONFLICT (supplier_id, purchase_order_no, warehouse_id, sku_id) DO UPDATE SET
            promised_date = EXCLUDED.promised_date,
            order_date = EXCLUDED.order_date,
            receipt_date = EXCLUDED.receipt_date,
            delay_reason = EXCLUDED.delay_reason,
            recorded_at = CURRENT_TIMESTAMP
        """
    )
    records = data[
        [
            "supplier_id",
            "warehouse_id",
            "sku_id",
            "purchase_order_no",
            "promised_date",
            "order_date",
            "receipt_date",
            "delay_reason",
        ]
    ].where(pd.notnull(data), None).to_dict("records")
    session.execute(statement, records)
    return len(records)


def ingest_dataset(session: Session, dataset_type: str, file_path: str | Path) -> dict[str, Any]:
    handlers = {
        "transactions": ingest_transactions,
        "snapshots": ingest_snapshots,
        "lead_times": ingest_lead_times,
    }
    try:
        handler = handlers[dataset_type]
    except KeyError as exc:
        raise IngestionError(f"Unsupported dataset_type: {dataset_type}") from exc
    row_count = handler(session, file_path)
    return {"dataset_type": dataset_type, "rows_processed": row_count, "file_path": str(file_path)}
