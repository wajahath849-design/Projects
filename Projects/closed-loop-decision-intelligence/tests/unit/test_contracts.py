import ast

from src.common.config import ROOT


def test_ground_truth_is_not_consumed_by_analytics():
    for folder in ["anomaly_detection", "investigation", "forecasting", "decision_engine", "impact", "metrics"]:
        for file in (ROOT/"src"/folder).glob("*.py"):
            tree = ast.parse(file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    assert node.attr != "simulation_ground_truth"
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert "simulation_ground_truth" not in node.value


def test_generated_sql_contract_matches_portable_query():
    import re
    portable = (ROOT/"sql/analytics/cohort_mart.sql").read_text()
    dbt = (ROOT/"dbt/models/intermediate/int_cohort_activity.sql").read_text()
    expected = re.sub(r"raw\.(\w+)", lambda match: "{{ ref('stg_"+match[1]+"') }}", portable)
    assert dbt == expected
