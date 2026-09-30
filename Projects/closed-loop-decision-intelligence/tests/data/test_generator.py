import pandas as pd

from src.synthetic_data.generator import generate


def test_generator_reproducible_and_linked():
    a, truth = generate(12, 42)
    b, _ = generate(12, 42)
    pd.testing.assert_frame_equal(a["web_sessions"], b["web_sessions"])
    assert set(a["payments"].order_id) == set(a["orders"].id)
    assert set(a["orders"].cohort_id) <= set(a["web_sessions"].id)
    assert len(truth) == 7
    assert a["web_sessions"].timestamp.nunique() >= 365
