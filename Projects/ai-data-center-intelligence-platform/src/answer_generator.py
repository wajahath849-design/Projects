from __future__ import annotations

import pandas as pd


class GroundedAnswerGenerator:
    """Deterministic answer renderer; it can only describe returned database values."""

    def generate(self, question: str, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "No matching records were found for that question."
        if len(frame) == 1:
            values = ", ".join(f"{column}: {self._format(value)}" for column, value in frame.iloc[0].items())
            return f"The database result is {values}."
        preview = frame.head(5)
        if len(frame.columns) == 2:
            first, second = frame.columns
            values = "; ".join(
                f"{self._format(row[first])}: {self._format(row[second])}" for _, row in preview.iterrows()
            )
            suffix = "" if len(frame) <= 5 else f" The table contains {len(frame)} rows in total."
            return f"The results are {values}.{suffix}"
        return f"The query returned {len(frame)} rows. The result table below is the authoritative answer."

    @staticmethod
    def _format(value) -> str:
        if pd.isna(value):
            return "not available"
        if isinstance(value, float):
            return f"{value:,.2f}"
        return str(value)
