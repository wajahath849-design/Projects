from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session


RISK_PRIORITY = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}


@dataclass
class NodeRequirement:
    recommendation_id: int
    sku_id: int
    warehouse_id: int
    region: str
    inventory_position: float
    target_stock: float
    gross_order_qty: float
    order_multiple: float
    risk_band: str


@dataclass(frozen=True)
class TransferProposal:
    sku_id: int
    from_warehouse_id: int
    to_warehouse_id: int
    transfer_qty: float
    receiver_recommendation_id: int


def build_transfer_plan(nodes: Iterable[NodeRequirement]) -> list[TransferProposal]:
    grouped: dict[int, list[NodeRequirement]] = defaultdict(list)
    for node in nodes:
        grouped[node.sku_id].append(node)

    proposals: list[TransferProposal] = []
    for sku_id, sku_nodes in grouped.items():
        donors = [
            {
                "node": node,
                "available": max(0.0, node.inventory_position - node.target_stock),
            }
            for node in sku_nodes
            if node.inventory_position > node.target_stock
        ]
        receivers = [node for node in sku_nodes if node.gross_order_qty > 0]
        receivers.sort(key=lambda node: (RISK_PRIORITY.get(node.risk_band, 99), -node.gross_order_qty))

        for receiver in receivers:
            remaining = receiver.gross_order_qty
            donors.sort(
                key=lambda donor: (
                    0 if donor["node"].region == receiver.region else 1,
                    -float(donor["available"]),
                )
            )
            for donor in donors:
                if remaining <= 0:
                    break
                available = float(donor["available"])
                if available <= 0 or donor["node"].warehouse_id == receiver.warehouse_id:
                    continue
                raw_qty = min(available, remaining)
                multiple = max(1.0, receiver.order_multiple)
                transfer_qty = math.floor(raw_qty / multiple) * multiple
                if transfer_qty <= 0:
                    continue
                proposals.append(
                    TransferProposal(
                        sku_id=sku_id,
                        from_warehouse_id=donor["node"].warehouse_id,
                        to_warehouse_id=receiver.warehouse_id,
                        transfer_qty=transfer_qty,
                        receiver_recommendation_id=receiver.recommendation_id,
                    )
                )
                donor["available"] = available - transfer_qty
                remaining -= transfer_qty
    return proposals


def run_network_rebalancing(session: Session, model_run_id: int) -> int:
    # Rebuild the proposed plan from scratch so reruns cannot leave stale transfers.
    session.execute(
        text("DELETE FROM inventory.inventory_transfer_recommendations WHERE model_run_id = :model_run_id AND status = 'PROPOSED'"),
        {"model_run_id": model_run_id},
    )
    session.execute(
        text("UPDATE inventory.replenishment_recommendations SET recommended_order_qty = gross_recommended_order_qty WHERE model_run_id = :model_run_id"),
        {"model_run_id": model_run_id},
    )
    rows = session.execute(
        text(
            """
            SELECT
                r.recommendation_id,
                r.sku_id,
                r.warehouse_id,
                w.region,
                r.inventory_position_qty,
                r.target_stock_qty,
                r.gross_recommended_order_qty,
                sku.order_multiple,
                r.risk_band
            FROM inventory.replenishment_recommendations r
            JOIN inventory.dim_warehouse w ON w.warehouse_id = r.warehouse_id
            JOIN inventory.dim_sku sku ON sku.sku_id = r.sku_id
            WHERE r.model_run_id = :model_run_id
            """
        ),
        {"model_run_id": model_run_id},
    ).mappings()
    nodes = [
        NodeRequirement(
            recommendation_id=int(row["recommendation_id"]),
            sku_id=int(row["sku_id"]),
            warehouse_id=int(row["warehouse_id"]),
            region=str(row["region"]),
            inventory_position=float(row["inventory_position_qty"]),
            target_stock=float(row["target_stock_qty"]),
            gross_order_qty=float(row["gross_recommended_order_qty"]),
            order_multiple=float(row["order_multiple"]),
            risk_band=str(row["risk_band"]),
        )
        for row in rows
    ]
    proposals = build_transfer_plan(nodes)
    inbound_by_recommendation: dict[int, float] = defaultdict(float)
    for proposal in proposals:
        inbound_by_recommendation[proposal.receiver_recommendation_id] += proposal.transfer_qty

    if proposals:
        session.execute(
            text(
                """
                INSERT INTO inventory.inventory_transfer_recommendations
                    (model_run_id, sku_id, from_warehouse_id, to_warehouse_id, transfer_qty)
                VALUES
                    (:model_run_id, :sku_id, :from_warehouse_id, :to_warehouse_id, :transfer_qty)
                ON CONFLICT (model_run_id, sku_id, from_warehouse_id, to_warehouse_id) DO UPDATE SET
                    transfer_qty = EXCLUDED.transfer_qty,
                    status = 'PROPOSED',
                    created_at = CURRENT_TIMESTAMP
                """
            ),
            [
                {
                    "model_run_id": model_run_id,
                    "sku_id": p.sku_id,
                    "from_warehouse_id": p.from_warehouse_id,
                    "to_warehouse_id": p.to_warehouse_id,
                    "transfer_qty": p.transfer_qty,
                }
                for p in proposals
            ],
        )

    for recommendation_id, inbound_qty in inbound_by_recommendation.items():
        session.execute(
            text(
                """
                UPDATE inventory.replenishment_recommendations
                SET recommended_order_qty = GREATEST(0, gross_recommended_order_qty - :inbound_qty)
                WHERE recommendation_id = :recommendation_id
                """
            ),
            {"inbound_qty": inbound_qty, "recommendation_id": recommendation_id},
        )
    session.commit()
    return len(proposals)
