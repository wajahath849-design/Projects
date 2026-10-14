from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from src.utils.common import file_hash


REQUIRED = {
    "projects": {"project_id", "client_id", "manager_id", "primary_department_id", "start_date", "planned_end_date", "completion_pct"},
    "departments": {"department_id", "department_name"},
    "categories": {"category_id", "category_name", "cost_group"},
    "clients": {"client_id", "client_name"},
    "managers": {"manager_id", "manager_name"},
    "budgets": {"budget_record_id", "project_id", "version_id", "version_number", "approval_status", "approved_date", "department_id", "allocated_budget_usd"},
    "costs": {"transaction_id", "project_id", "department_id", "category_id", "transaction_date", "amount", "currency"},
    "revenue": {"revenue_id", "project_id", "recognition_date", "recognized_revenue_usd", "currency"},
}


def read_sources(raw_dir: Path) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    data, metadata = {}, []
    for name, required in REQUIRED.items():
        path = raw_dir / ("budgets.xlsx" if name == "budgets" and (raw_dir / "budgets.xlsx").exists() else f"{name}.csv")
        if not path.exists():
            raise FileNotFoundError(f"Missing required source: {path}")
        frame = pd.read_excel(path, dtype=str) if path.suffix == ".xlsx" else pd.read_csv(path, dtype=str, keep_default_na=False)
        frame.columns = [c.strip().lower() for c in frame.columns]
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name}: missing columns {sorted(missing)}")
        data[name] = frame
        metadata.append({"source": name, "path": str(path.relative_to(raw_dir.parent.parent)),
                         "sha256": file_hash(path), "rows": len(frame), "bytes": path.stat().st_size,
                         "modified_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    return data, metadata
