from app.network_rebalancing import NodeRequirement, build_transfer_plan


def test_internal_surplus_reduces_external_need() -> None:
    nodes = [
        NodeRequirement(1, 10, 100, "North", 500, 300, 0, 10, "LOW"),
        NodeRequirement(2, 10, 200, "North", 50, 250, 200, 10, "CRITICAL"),
    ]
    plan = build_transfer_plan(nodes)
    assert len(plan) == 1
    assert plan[0].from_warehouse_id == 100
    assert plan[0].to_warehouse_id == 200
    assert plan[0].transfer_qty == 200


def test_transfer_respects_order_multiple() -> None:
    nodes = [
        NodeRequirement(1, 10, 100, "North", 355, 300, 0, 25, "LOW"),
        NodeRequirement(2, 10, 200, "South", 50, 250, 200, 25, "HIGH"),
    ]
    plan = build_transfer_plan(nodes)
    assert plan[0].transfer_qty == 50
