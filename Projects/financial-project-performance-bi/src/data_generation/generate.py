"""Deterministic synthetic source generation. All amounts are fictional USD."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.utils.common import month_start, path_from_config, settings


def generate(raw_dir: Path | None = None) -> dict[str, int]:
    cfg = settings()
    out = raw_dir or path_from_config("raw_dir")
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(cfg["seed"])
    as_of = pd.Timestamp(cfg["as_of_date"])
    departments = pd.DataFrame({"department_id": [f"D{i:02}" for i in range(1, 7)],
        "department_name": ["Software", "Infrastructure", "Engineering", "Consulting", "Operations", "Data"]})
    categories = pd.DataFrame({"category_id": [f"C{i:02}" for i in range(1, 7)],
        "category_name": ["Employees", "Contractors", "Procurement", "Cloud", "Travel", "Operations"],
        "cost_group": ["Labor", "Labor", "Nonlabor", "Nonlabor", "Nonlabor", "Nonlabor"]})
    clients = pd.DataFrame({"client_id": [f"CL{i:02}" for i in range(1, 13)],
        "client_name": [f"Fictional Client {i:02}" for i in range(1, 13)]})
    managers = pd.DataFrame({"manager_id": [f"M{i:02}" for i in range(1, 10)],
        "manager_name": [f"Demo Manager {i:02}" for i in range(1, 10)]})
    for name, frame in {"departments": departments, "categories": categories,
                        "clients": clients, "managers": managers}.items():
        frame.to_csv(out / f"{name}.csv", index=False)

    project_rows, budget_rows, cost_rows, revenue_rows = [], [], [], []
    for i in range(1, cfg["project_count"] + 1):
        pid = f"P{i:03}"
        tag = {1: "over_budget", 2: "declining_margin", 3: "forecast_overrun"}.get(i, "standard")
        if i <= 3:
            start = pd.Timestamp("2025-01-01")
            end = pd.Timestamp("2026-12-31")
        else:
            start = pd.Timestamp("2024-01-01") + pd.DateOffset(months=int(rng.integers(0, 25)))
            end = start + pd.DateOffset(months=int(rng.integers(12, 30))) - pd.Timedelta(days=1)
        budget = float(int(rng.integers(350_000, 1_700_000) / 1000) * 1000)
        if i == 1:
            budget = 480_000.0
        elif i == 2:
            budget = 680_000.0
        elif i == 3:
            budget = 800_000.0
        primary = f"D{int(rng.integers(1, 7)):02}"
        secondary = f"D{(int(primary[1:]) % 6) + 1:02}"
        status = "Complete" if end <= as_of else "Active"
        progress = 1.0 if status == "Complete" else min(0.95, max(0.08, (as_of - start).days / max((end - start).days, 1)))
        project_rows.append({"project_id": pid, "project_name": f"Project {i:03} — {['Platform', 'Integration', 'Engineering', 'Advisory'][i % 4]}",
            "client_id": f"CL{((i - 1) % 12) + 1:02}", "manager_id": f"M{((i - 1) % 9) + 1:02}",
            "primary_department_id": primary, "start_date": start.date(), "planned_end_date": end.date(),
            "status": status, "completion_pct": round(progress, 4), "scenario_tag": tag,
            "contract_value_usd": round(budget * (1.25 if i == 2 else float(rng.uniform(1.24, 1.62))), 2)})
        versions = [("V1", start, budget * (0.9 if i % 4 == 0 else 1.0), "Approved")]
        if i % 4 == 0:
            versions.append(("V2", min(start + pd.DateOffset(months=6), as_of), budget, "Approved"))
        for version, approved, amount, approval_status in versions:
            for dept, share in [(primary, 0.7), (secondary, 0.3)]:
                budget_rows.append({"budget_record_id": f"B-{pid}-{version}-{dept}", "project_id": pid,
                    "version_id": f"{pid}-{version}", "version_number": int(version[1:]),
                    "approval_status": approval_status, "approved_date": approved.date(),
                    "department_id": dept, "allocated_budget_usd": round(amount * share, 2)})
        months = pd.date_range(month_start(start), month_start(min(end, as_of)), freq="MS")
        planned_months = max(len(pd.date_range(month_start(start), month_start(end), freq="MS")), 1)
        base_monthly = budget / planned_months
        for m_idx, month in enumerate(months):
            phase = 1.0 + 0.18 * np.sin((m_idx / planned_months) * np.pi)
            monthly_cost = base_monthly * phase * float(rng.uniform(0.82, 1.12))
            if i == 1:
                monthly_cost *= 1.75 if month >= pd.Timestamp("2026-01-01") else 1.15
            elif i == 2:
                monthly_cost *= 1.7 if month >= pd.Timestamp("2026-04-01") else 0.9
            elif i == 3:
                monthly_cost *= 0.98
            elif i % 11 == 0:
                monthly_cost *= 0.64
            elif i % 13 == 0:
                monthly_cost *= 1.25
            weights = np.array([0.52, 0.22, 0.12, 0.08, 0.03, 0.03])
            if i in (1, 2) and month >= pd.Timestamp("2026-01-01"):
                weights = np.array([0.32, 0.46, 0.12, 0.06, 0.02, 0.02])
            weights = weights / weights.sum()
            for j in range(10):
                category = str(rng.choice(categories.category_id.to_numpy(), p=weights))
                day = min(int(rng.integers(1, 28)), (month + pd.offsets.MonthEnd()).day)
                cost_rows.append({"transaction_id": f"T-{pid}-{m_idx:02}-{j:02}", "project_id": pid,
                    "department_id": primary if j < 7 else secondary, "category_id": category,
                    "transaction_date": (month + pd.Timedelta(days=day - 1)).date(),
                    "amount": round(monthly_cost / 10 * float(rng.uniform(0.8, 1.2)), 2), "currency": "USD",
                    "description": "Synthetic demonstration cost"})
            if m_idx > 3 and m_idx % 7 == 0:
                cost_rows.append({"transaction_id": f"T-{pid}-{m_idx:02}-ADJ", "project_id": pid,
                    "department_id": primary, "category_id": "C01", "transaction_date": (month + pd.Timedelta(days=20)).date(),
                    "amount": -round(monthly_cost * 0.015, 2), "currency": "USD", "description": "Valid accounting correction"})
            revenue_factor = 0.82 if i == 2 and month >= pd.Timestamp("2026-04-01") else 1.0
            recognized = float(project_rows[-1]["contract_value_usd"]) / planned_months * revenue_factor
            revenue_rows.append({"revenue_id": f"R-{pid}-{m_idx:02}", "project_id": pid,
                "recognition_date": (month + pd.offsets.MonthEnd()).date(),
                "recognized_revenue_usd": round(recognized, 2), "currency": "USD"})

    projects = pd.DataFrame(project_rows)
    costs = pd.DataFrame(cost_rows)
    # Deliberate invalid records exercise quarantine; negative accounting corrections remain valid.
    bad = costs.iloc[:4].copy()
    bad.loc[bad.index[0], "transaction_id"] = costs.iloc[0]["transaction_id"]
    bad.loc[bad.index[1], "transaction_id"] = "T-BAD-MISSING"
    bad.loc[bad.index[1], "project_id"] = ""
    bad.loc[bad.index[2], "transaction_id"] = "T-BAD-CATEGORY"
    bad.loc[bad.index[2], "category_id"] = "C99"
    bad.loc[bad.index[3], "transaction_id"] = "T-BAD-DATE"
    bad.loc[bad.index[3], "transaction_date"] = "2023-01-01"
    costs = pd.concat([costs, bad], ignore_index=True)
    for name, frame in {"projects": projects, "costs": costs, "revenue": pd.DataFrame(revenue_rows),
                        "budgets": pd.DataFrame(budget_rows)}.items():
        frame.to_csv(out / f"{name}.csv", index=False)
    return {"projects": len(projects), "costs": len(costs), "revenue": len(revenue_rows), "budgets": len(budget_rows)}


if __name__ == "__main__":
    print(generate())
