from __future__ import annotations

import pandas as pd


def chart_spec(frame: pd.DataFrame) -> dict | None:
    if frame.empty or len(frame) == 1:
        return None
    numeric = list(frame.select_dtypes(include="number").columns)
    if not numeric:
        return None
    x = next((column for column in frame.columns if "date" in column.lower() or "year" in column.lower() or "time" in column.lower()), frame.columns[0])
    kind = "line" if x != frame.columns[0] or any(token in x.lower() for token in ("date", "year", "time")) else "bar"
    return {"kind": kind, "x": x, "y": numeric[0]}


def build_plotly_chart(frame: pd.DataFrame, spec: dict | None = None):
    spec = spec or chart_spec(frame)
    if spec is None:
        return None
    import plotly.express as px
    return px.line(frame, x=spec["x"], y=spec["y"], markers=True) if spec["kind"] == "line" else px.bar(frame, x=spec["x"], y=spec["y"])
