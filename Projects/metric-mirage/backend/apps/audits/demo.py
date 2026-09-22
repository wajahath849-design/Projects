from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from .engine import AuditSpec, analyze_dataframe


def build_demo_frame() -> pd.DataFrame:
    """Build a deterministic dataset containing a real Simpson's-paradox pattern."""
    rng = np.random.default_rng(42)
    rows: list[dict] = []
    dates = pd.date_range("2026-01-05", periods=16, freq="W-MON")
    for week_index, current_date in enumerate(dates):
        after_launch = week_index >= 8
        for device in ("Desktop", "Mobile"):
            for region in ("DACH", "Benelux"):
                if after_launch:
                    base_sessions = 820 if device == "Desktop" else 210
                    conversion_rate = 0.074 if device == "Desktop" else 0.035
                else:
                    base_sessions = 210 if device == "Desktop" else 820
                    conversion_rate = 0.080 if device == "Desktop" else 0.041
                if region == "Benelux":
                    base_sessions = int(base_sessions * 0.55)
                    conversion_rate -= 0.003
                sessions = max(
                    20, int(base_sessions + rng.normal(0, base_sessions * 0.035))
                )
                conversions = int(
                    round(sessions * max(0, conversion_rate + rng.normal(0, 0.0015)))
                )
                rows.append(
                    {
                        "date": current_date.date().isoformat(),
                        "device": device,
                        "region": region,
                        "sessions": sessions,
                        "conversions": conversions,
                        "revenue": round(
                            conversions
                            * (82 if device == "Desktop" else 61)
                            * rng.uniform(0.96, 1.04),
                            2,
                        ),
                        "release": "New checkout"
                        if after_launch
                        else "Previous checkout",
                    }
                )
    rows.append(dict(rows[-1]))
    rows[-1]["region"] = None
    return pd.DataFrame(rows)


def demo_spec() -> AuditSpec:
    return AuditSpec(
        metric_name="Checkout conversion",
        claim="The new checkout increased conversion by more than 20%.",
        numerator="conversions",
        denominator="sessions",
        date_column="date",
        segment_columns=["device", "region"],
        split_date="2026-03-02",
        audit_id="MM-DEMO-042",
    )


@lru_cache(maxsize=1)
def build_demo_result() -> dict:
    return analyze_dataframe(build_demo_frame(), demo_spec())
