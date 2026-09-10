import pandas as pd

from src.answer_generator import GroundedAnswerGenerator
from src.answer_validator import validate_answer_numbers


def test_generated_answer_is_numerically_grounded():
    frame = pd.DataFrame({"facility": ["Frankfurt"], "average_pue": [1.31]})
    answer = GroundedAnswerGenerator().generate("question", frame)
    assert validate_answer_numbers(answer, frame)[0]


def test_unsupported_number_is_detected():
    frame = pd.DataFrame({"value": [10]})
    assert not validate_answer_numbers("The value is 99.", frame)[0]


def test_question_filter_year_may_be_repeated_in_answer():
    frame = pd.DataFrame({"facility": ["Sydney"], "average_latency": [12.99]})
    assert validate_answer_numbers(
        "In 2025, Sydney had average latency of 12.99 ms.", frame, "Which facility in 2025?"
    )[0]
