"""SQL contract: observed zero retention is different from an immature cell."""
import sqlite3
from pathlib import Path

import pandas as pd


def test_cohort_zero_activity_and_future_cells():
    orders = pd.DataFrame({"customer_id": ["A", "B", "A", "C", "D"],
        "invoice_date": ["2011-01-02", "2011-01-03", "2011-03-02", "2011-03-05", "2011-04-01"]})
    with sqlite3.connect(":memory:") as con:
        orders.to_sql("orders", con, index=False)
        sql = (Path(__file__).resolve().parents[1] / "sql/cohorts.sql").read_text()
        rows = pd.read_sql_query(sql, con, params={"period_end": "2011-04-01"})
    january = rows[rows.cohort == "2011-01"].set_index("age_month")
    assert list(january.retention) == [1., 0., .5]
    assert list(rows[rows.cohort == "2011-03"].age_month) == [0]
    assert "2011-04" not in set(rows.cohort)
