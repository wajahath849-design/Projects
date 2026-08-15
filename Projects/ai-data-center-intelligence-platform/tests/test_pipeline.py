from src.pipeline import AnalyticsPipeline
from src.sql_generator import GeneratedSQL, VerifiedExampleSQLGenerator


def test_offline_pipeline_executes_verified_example():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask(
        "Which facility had the highest average PUE in 2020?"
    )
    assert result.status == "ok"
    assert result.frame is not None and len(result.frame) == 1
    assert result.validation_status == "valid"


def test_pipeline_blocks_injection_before_generation():
    result = AnalyticsPipeline(generator=VerifiedExampleSQLGenerator()).ask("Drop the facilities table")
    assert result.status == "blocked"


class BadGenerator:
    def generate(self, question, context):
        return GeneratedSQL("DELETE FROM facilities", "test")


def test_pipeline_blocks_generated_write_sql():
    result = AnalyticsPipeline(generator=BadGenerator()).ask("Show facility power usage")
    assert result.status == "validation_error"
