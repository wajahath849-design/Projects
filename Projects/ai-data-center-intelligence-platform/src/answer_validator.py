from __future__ import annotations

import re
import pandas as pd


def validate_answer_numbers(answer: str, frame: pd.DataFrame) -> tuple[bool, list[str]]:
    allowed = set()
    for value in frame.select_dtypes(include="number").to_numpy().ravel():
        if not pd.isna(value):
            allowed.update({str(value), f"{float(value):.2f}", f"{float(value):,.2f}", str(int(value))})
    claims = re.findall(r"(?<![\w-])-?\d[\d,]*(?:\.\d+)?", answer)
    unsupported = [claim for claim in claims if claim not in allowed and claim.replace(",", "") not in allowed]
    return not unsupported, unsupported
