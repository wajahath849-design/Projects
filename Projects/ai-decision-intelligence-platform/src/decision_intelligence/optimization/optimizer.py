"""Mixed-integer replenishment model and programmatic constraint validation."""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import Any

import pandas as pd
from ortools.linear_solver import pywraplp


@dataclass(frozen=True)
class OptimizationSolution:
    """Solver output plus validation diagnostics."""

    status: str
    objective_value: float | None
    orders: pd.DataFrame
    diagnostics: tuple[str, ...]


STATUS_MAP = {
    pywraplp.Solver.OPTIMAL: "OPTIMAL",
    pywraplp.Solver.FEASIBLE: "FEASIBLE",
    pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
    pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
}


def solve_replenishment(
    candidates: pd.DataFrame,
    requirements: pd.DataFrame,
    budget: float,
    planning_horizon_days: int,
    time_limit_seconds: int,
    penalties: dict[str, float],
) -> OptimizationSolution:
    """Solve integer orders with supplier, warehouse, budget, and coverage constraints."""
    solver = pywraplp.Solver.CreateSolver("CBC_MIXED_INTEGER_PROGRAMMING")
    if solver is None:
        return OptimizationSolution("ERROR", None, pd.DataFrame(), ("CBC solver unavailable",))
    solver.SetTimeLimit(time_limit_seconds * 1000)
    quantity: dict[Hashable, Any] = {}
    active: dict[Hashable, Any] = {}
    objective = solver.Objective()
    for index, row in candidates.iterrows():
        cap = min(
            float(row["maximum_order_quantity"]),
            float(row["daily_capacity"]) * planning_horizon_days,
        )
        quantity[index] = solver.IntVar(0, cap, f"quantity_{index}")
        active[index] = solver.BoolVar(f"active_{index}")
        solver.Add(quantity[index] <= cap * active[index])
        solver.Add(
            quantity[index] >= float(row["minimum_order_quantity"]) * active[index]
        )
        variable_cost = (
            float(row["purchase_cost"])
            + float(row["shipping_cost_per_unit"])
            + float(row["holding_cost_per_unit_day"]) * planning_horizon_days / 2
            + penalties["late"] * float(row["delay_probability"])
        )
        objective.SetCoefficient(quantity[index], variable_cost)
        objective.SetCoefficient(active[index], float(row["base_shipping_cost"]))
    for requirement_index, requirement in requirements.iterrows():
        eligible = candidates[
            (candidates["product_key"] == requirement["product_key"])
            & (candidates["warehouse_key"] == requirement["warehouse_key"])
        ].index
        ordered = solver.Sum(quantity[index] for index in eligible)
        required = float(requirement["required_quantity"])
        shortage = solver.NumVar(0, solver.infinity(), f"shortage_{requirement_index}")
        excess = solver.NumVar(0, solver.infinity(), f"excess_{requirement_index}")
        solver.Add(ordered >= required)
        solver.Add(shortage >= required - ordered)
        solver.Add(excess >= ordered - required)
        objective.SetCoefficient(shortage, penalties["stockout"])
        objective.SetCoefficient(excess, penalties["excess"])
    for _, group in candidates.groupby("supplier_key"):
        supplier_capacity = float(group["supplier_daily_capacity"].iloc[0])
        solver.Add(
            solver.Sum(quantity[index] for index in group.index)
            <= supplier_capacity * planning_horizon_days
        )
    for _, group in candidates.groupby("warehouse_key"):
        available = float(group["warehouse_available_capacity"].iloc[0])
        solver.Add(solver.Sum(quantity[index] for index in group.index) <= available)
    solver.Add(solver.Sum(
        quantity[index] * (
            float(candidates.loc[index, "purchase_cost"])
            + float(candidates.loc[index, "shipping_cost_per_unit"])
        )
        + active[index] * float(candidates.loc[index, "base_shipping_cost"])
        for index in candidates.index
    ) <= budget)
    objective.SetMinimization()
    status_code = solver.Solve()
    status = STATUS_MAP.get(status_code, "ERROR")
    if status not in {"OPTIMAL", "FEASIBLE"}:
        message = (
            "No feasible order plan satisfies demand coverage, supplier and warehouse "
            f"capacity, MOQ/maximum order, eligibility, lead-time, and budget={budget:.2f}."
        )
        return OptimizationSolution(status, None, pd.DataFrame(), (message,))
    rows = []
    for index, row in candidates.iterrows():
        value = quantity[index].solution_value()
        if value > 0.5:
            rows.append({**row.to_dict(), "recommended_order_quantity": value})
    orders = pd.DataFrame(rows)
    diagnostics = validate_solution(
        candidates, requirements, orders, budget, planning_horizon_days
    )
    if diagnostics:
        return OptimizationSolution("ERROR", solver.Objective().Value(), orders, diagnostics)
    return OptimizationSolution(status, solver.Objective().Value(), orders, ())


def validate_solution(
    candidates: pd.DataFrame,
    requirements: pd.DataFrame,
    orders: pd.DataFrame,
    budget: float,
    planning_horizon_days: int,
    tolerance: float = 1e-6,
) -> tuple[str, ...]:
    """Independently verify every optimization constraint after solving."""
    failures: list[str] = []
    if orders.empty and float(requirements["required_quantity"].sum()) > tolerance:
        return ("Demand coverage failed: positive requirements but no orders",)
    for row in orders.to_dict(orient="records"):
        quantity = float(row["recommended_order_quantity"])
        if quantity < -tolerance or abs(quantity - round(quantity)) > tolerance:
            failures.append(f"Nonnegative integer constraint failed for row {row}")
        if quantity + tolerance < float(row["minimum_order_quantity"]):
            failures.append(
                f"MOQ failed for supplier-product "
                f"{row['supplier_key']}-{row['product_key']}"
            )
        cap = min(
            float(row["maximum_order_quantity"]),
            float(row["daily_capacity"]) * planning_horizon_days,
        )
        if quantity > cap + tolerance:
            failures.append(
                f"Maximum order failed for supplier-product "
                f"{row['supplier_key']}-{row['product_key']}"
            )
        total_lead_time = (
            float(row["lead_time_days"]) + float(row["average_transit_days"])
        )
        if total_lead_time > planning_horizon_days:
            failures.append(f"Lead-time feasibility failed for row {row}")
    for requirement in requirements.to_dict(orient="records"):
        supplied = 0.0 if orders.empty else float(orders.loc[
            (orders["product_key"] == requirement["product_key"])
            & (orders["warehouse_key"] == requirement["warehouse_key"]),
            "recommended_order_quantity",
        ].sum())
        if supplied + tolerance < float(requirement["required_quantity"]):
            failures.append(
                f"Demand coverage failed for product {requirement['product_key']} "
                f"warehouse {requirement['warehouse_key']}"
            )
    if not orders.empty:
        for supplier_key, group in orders.groupby("supplier_key"):
            capacity = float(group["supplier_daily_capacity"].iloc[0]) * planning_horizon_days
            if float(group["recommended_order_quantity"].sum()) > capacity + tolerance:
                failures.append(f"Supplier capacity failed for {supplier_key}")
        for warehouse_key, group in orders.groupby("warehouse_key"):
            capacity = float(group["warehouse_available_capacity"].iloc[0])
            if float(group["recommended_order_quantity"].sum()) > capacity + tolerance:
                failures.append(f"Warehouse capacity failed for {warehouse_key}")
        spend = float((
            orders["recommended_order_quantity"]
            * (orders["purchase_cost"] + orders["shipping_cost_per_unit"])
            + orders["base_shipping_cost"]
        ).sum())
        if spend > budget + tolerance:
            failures.append("Budget constraint failed")
        merged = orders.merge(
            candidates[["product_key", "supplier_key", "warehouse_key"]].drop_duplicates(),
            on=["product_key", "supplier_key", "warehouse_key"], how="left", indicator=True,
        )
        if (merged["_merge"] != "both").any():
            failures.append("Product-supplier or product-warehouse eligibility failed")
    return tuple(failures)
