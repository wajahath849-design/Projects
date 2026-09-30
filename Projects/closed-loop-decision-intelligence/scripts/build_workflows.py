"""Generate importable n8n workflows with an explicit human-approval boundary."""
import json
from uuid import NAMESPACE_URL, uuid5

from src.common.config import ROOT

STAGES = ["ingestion", "quality", "kpis", "anomalies", "investigation", "forecast", "decisions",
          "approvals", "actions", "impact", "memory"]
FILENAMES = ["data_ingestion", "data_quality_guardian", "kpi_engine", "anomaly_detector",
             "investigation_engine", "forecast_risk", "decision_engine", "human_approval",
             "action_orchestrator", "impact_verification", "decision_memory"]


def node(name, kind, parameters, x, version=1):
    return {"id": str(uuid5(NAMESPACE_URL, name)), "name": name, "type": "n8n-nodes-base."+kind,
            "typeVersion": version, "position": [x, 300], "parameters": parameters}


def http(name, url, x, workflow=False):
    result = node(name, "httpRequest", {"method": "POST", "url": url, "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "X-Workflow-Key" if workflow else "X-API-Key",
                                                 "value": "={{ $env.ANALYTICS_API_TOKEN }}"}]},
        "options": {"timeout": 300000}}, x, 4.2)
    result.update(retryOnFail=True, maxTries=3, waitBetweenTries=2000)
    return result


def build():
    folder = ROOT / "n8n/workflows"
    folder.mkdir(parents=True, exist_ok=True)
    for index, stage in enumerate(STAGES):
        nodes = [node("Manual start", "manualTrigger", {}, 0),
                 node("Authenticated stage webhook", "webhook", {"httpMethod": "POST", "path": "cldi-"+stage,
                      "authentication": "headerAuth", "responseMode": "onReceived", "options": {}}, 0, 2),
                 http("Run "+stage, "={{ $env.ANALYTICS_API_URL + '/orchestration/"+stage+"' }}", 250)]
        nodes[1]["webhookId"] = str(uuid5(NAMESPACE_URL, "cldi-"+stage))
        nodes[1]["credentials"] = {"httpHeaderAuth": {"name": "CLDI Workflow Header"}}
        connections = {"Manual start": {"main": [[{"node": "Run "+stage, "type": "main", "index": 0}]]},
                       "Authenticated stage webhook": {"main": [[{"node": "Run "+stage, "type": "main", "index": 0}]]}}

        def link(before, after, branch=0):
            outputs = connections.setdefault(before, {"main": [[]]})["main"]
            while len(outputs) <= branch:
                outputs.append([])
            outputs[branch].append({"node": after, "type": "main", "index": 0})

        tail = "Run "+stage
        if stage in ("ingestion", "approvals", "impact"):
            interval = {"field": "hours", "hoursInterval": 24} if stage == "ingestion" else {"field": "minutes", "minutesInterval": 5}
            nodes.append(node("Schedule", "scheduleTrigger", {"rule": {"interval": [interval]}}, 0, 1.2))
            link("Schedule", tail)
        if stage == "approvals":
            nodes.append(node("Approved by human", "if", {"conditions": {"options": {"caseSensitive": True,
                "leftValue": "", "typeValidation": "strict", "version": 2},
                "conditions": [{"id": "approved", "leftValue": "={{ $json.status }}", "rightValue": "APPROVED",
                                "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"},
                "options": {}}, 500, 2.2))
            link(tail, "Approved by human")
            tail = "Approved by human"
        if stage == "actions":
            nodes.append(node("Split actions", "splitOut", {"fieldToSplitOut": "action_ids", "options": {}}, 500, 1))
            link(tail, "Split actions")
            nodes.append(http("Advance simulated source", "={{ $env.ANALYTICS_API_URL + '/simulation/advance/' + $json.action_ids }}", 750))
            link("Split actions", "Advance simulated source")
            nodes.append(node("Observation wait", "wait", {"amount": 1, "unit": "minutes"}, 1000, 1.1))
            link("Advance simulated source", "Observation wait")
            tail = "Observation wait"
        if stage != "memory":
            next_stage = STAGES[index+1]
            nodes.append(http("Trigger "+next_stage, "={{ 'http://n8n:5678/webhook/cldi-"+next_stage+"' }}", 1250, workflow=True))
            link(tail, "Trigger "+next_stage)
        workflow = {"id": "cldi"+str(index+1).zfill(2), "name": f"CLDI {index+1:02d} - {FILENAMES[index]}",
                    "nodes": nodes, "connections": connections, "active": False,
                    "settings": {"executionOrder": "v1", "saveDataErrorExecution": "all",
                                 "saveDataSuccessExecution": "none", "timezone": "UTC"},
                    "pinData": {}, "tags": []}
        (folder / f"{index+1:02d}_{FILENAMES[index]}.json").write_text(json.dumps(workflow, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build()
