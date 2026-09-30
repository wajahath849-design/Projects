import pandas as pd

from src.data_quality.guardian import validate


def test_stale_feed_and_missing_payments_fail_closed():
    sessions = pd.DataFrame([dict(id="s", timestamp=pd.Timestamp("2026-01-01"), sessions=100,
                                  server_sessions=100, country="Germany", device="Mobile", channel="Direct")])
    orders = pd.DataFrame([dict(id="o", cohort_id="s", customer_id="c", amount=10., status="PAID")])
    payments = pd.DataFrame([dict(id="p", order_id="missing", status="PAID")])
    report = validate({"web_sessions": sessions, "orders": orders, "payments": payments}, "2026-01-05")
    assert report.quarantined
    failed = {c["check_type"] for c in report.checks if c["status"] == "FAIL"}
    assert {"freshness", "referential_integrity"} <= failed
