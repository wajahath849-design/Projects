import json

from src.common.config import ROOT


def test_workflow_graphs_and_approval_boundary():
    files = sorted((ROOT/"n8n/workflows").glob("*.json"))
    assert len(files) == 11
    for path in files:
        flow = json.loads(path.read_text())
        names = {n["name"] for n in flow["nodes"]}
        assert flow["active"] is False
        for name, edges in flow["connections"].items():
            assert name in names
            assert all(edge["node"] in names for branch in edges["main"] for edge in branch)
        assert "APPROVAL_TOKEN" not in path.read_text()
        for node in flow["nodes"]:
            if node["type"].endswith("httpRequest"):
                assert "/approve'" not in node["parameters"]["url"]
    approval = json.loads(files[7].read_text())
    assert any(n["type"].endswith(".if") for n in approval["nodes"])
