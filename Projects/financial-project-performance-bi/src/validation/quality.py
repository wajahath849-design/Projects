from __future__ import annotations

import pandas as pd
import numpy as np


def clean_fact(frame: pd.DataFrame, *, source: str, id_col: str, amount_col: str,
               date_col: str, projects: pd.DataFrame, departments: pd.DataFrame | None = None,
               categories: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Quarantine invalid rows; retain negative adjustments and a row-level reason."""
    f = frame.copy().reset_index(drop=True)
    for col in (id_col, "project_id", "department_id", "category_id"):
        if col in f:
            f[col] = f[col].fillna("").astype(str).str.strip()
    f["source_row"] = f.index + 2
    reasons = pd.Series("", index=f.index, dtype=str)

    def flag(mask, reason):
        nonlocal reasons
        reasons = reasons.mask(mask & reasons.eq(""), reason)

    flag(f[id_col].fillna("").astype(str).str.strip().eq(""), "missing_identifier")
    flag(f.duplicated(id_col, keep="first"), "duplicate_identifier")
    flag(f.project_id.eq(""), "missing_project_identifier")
    flag(~f.project_id.isin(projects.project_id), "invalid_project")
    if departments is not None and "department_id" in f:
        flag(~f.department_id.isin(departments.department_id), "invalid_department")
    if categories is not None and "category_id" in f:
        flag(~f.category_id.isin(categories.category_id), "invalid_category")
    f[date_col] = pd.to_datetime(f[date_col], errors="coerce")
    flag(f[date_col].isna(), "invalid_date")
    starts = projects.set_index("project_id").start_date
    early = f[date_col] < f.project_id.map(starts)
    flag(early.fillna(False), "date_before_project_start")
    f[amount_col] = pd.to_numeric(f[amount_col], errors="coerce")
    flag(f[amount_col].isna() | ~np.isfinite(f[amount_col]), "invalid_amount")
    if "currency" in f:
        f["currency"] = f.currency.fillna("").astype(str).str.upper().str.strip()
        flag(f.currency.ne("USD"), "unsupported_currency")
    rejected = f.loc[reasons.ne("")].copy()
    rejected["source"] = source
    rejected["reason"] = reasons[reasons.ne("")].to_numpy()
    valid = f.loc[reasons.eq("")].copy()
    return valid.drop(columns="source_row"), rejected[["source", "source_row", id_col, "reason"]].rename(columns={id_col: "record_id"})


def assert_referential_integrity(tables: dict[str, pd.DataFrame]) -> None:
    projects = set(tables["DimProject"].project_id)
    dates = set(tables["DimDate"].date_key)
    for name in ("FactBudget", "FactActualCost", "FactRevenue", "FactForecast"):
        fact = tables[name]
        if not set(fact.project_id).issubset(projects):
            raise AssertionError(f"{name}: orphan project")
        if not set(fact.date_key).issubset(dates):
            raise AssertionError(f"{name}: orphan date")
    if not set(tables["FactActualCost"].category_id).issubset(set(tables["DimCostCategory"].category_id)):
        raise AssertionError("FactActualCost: orphan category")
    if not set(tables["FactBudget"].department_id).issubset(set(tables["DimDepartment"].department_id)):
        raise AssertionError("FactBudget: orphan department")
