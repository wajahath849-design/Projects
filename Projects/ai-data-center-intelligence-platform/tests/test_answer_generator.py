import pandas as pd

from src.answer_generator import OllamaGroundedAnswerGenerator


def test_ordinary_database_result_does_not_need_answer_llm():
    frame = pd.DataFrame([{"facility_name": "Frankfurt Central", "average_pue": 1.42}])
    assert not OllamaGroundedAnswerGenerator.will_use_llm(
        "Which facility had the highest PUE?", frame
    )


def test_investigative_result_can_use_answer_llm():
    frame = pd.DataFrame([
        {"month": "2025-07", "average_pue": 1.62, "cooling_power_kw": 420.0}
    ])
    assert OllamaGroundedAnswerGenerator.will_use_llm(
        "Why did PUE increase and what coincided with it?", frame
    )
