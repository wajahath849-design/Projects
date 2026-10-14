from __future__ import annotations

import pandas as pd


def select_approved_budget(budget: pd.DataFrame, as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select one lifetime version per project, retaining all allocations in that version."""
    eligible = budget[(budget.approval_status.str.lower() == "approved") & (budget.approved_date <= as_of)]
    selected = eligible.sort_values(["project_id", "approved_date", "version_number"]).drop_duplicates("project_id", keep="last")
    selected_versions = selected[["project_id", "version_id"]].drop_duplicates()
    selected_budget = budget.merge(selected_versions, on=["project_id", "version_id"], how="inner")
    versions = budget[["version_id", "project_id", "version_number", "approval_status", "approved_date"]].drop_duplicates().copy()
    versions["is_selected_approved"] = versions.version_id.isin(selected_versions.version_id)
    return selected_budget, versions
