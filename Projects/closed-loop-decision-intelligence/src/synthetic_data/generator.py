"""Generate linked transactions and daily operational cohort snapshots.

Scenario labels leave this module only in a separate evaluation-only return value.
Nothing in the analytics path imports or queries that return value.
"""
from datetime import datetime, timedelta
from itertools import product

import numpy as np
import pandas as pd

COUNTRIES = ["Germany", "France", "Netherlands", "Spain", "Italy", "United Kingdom"]
DEVICES = ["Desktop", "Mobile", "Tablet"]
CHANNELS = ["Organic Search", "Paid Search", "Paid Social", "Email", "Direct", "Referral", "Affiliate"]
CATEGORIES = ["Software", "Accessories", "Learning"]
SEGMENTS = ["Consumer", "Professional", "Small Business"]


def scenario_registry(end: datetime) -> list[dict]:
    definitions = [
        ("001", "business", 6, 6, "Germany", "Mobile", "*", "*", "deployment", "conversion", -0.65),
        ("002", "business", 210, 7, "*", "*", "Paid Social", "*", "campaign_efficiency", "cac", 1.8),
        ("003", "business", 170, 7, "*", "*", "*", "Accessories", "inventory", "orders", -0.55),
        ("004", "business", 130, 14, "France", "*", "*", "*", "support", "support_volume", 3.0),
        ("005", "business", 95, 6, "*", "*", "*", "*", "payment_provider", "payment_failure_rate", 4.0),
        ("006", "data_quality", 50, 5, "*", "*", "*", "*", "tracking", "traffic", -0.8),
        ("007", "planned", 245, 4, "*", "*", "Email", "*", "promotion", "revenue", 0.6),
    ]
    return [dict(id=i, incident_type=kind, start_time=end-timedelta(days=offset),
                 end_time=end-timedelta(days=offset-duration), affected_country=country,
                 affected_device=device, affected_channel=channel, affected_product=category,
                 expected_metric_effect={metric: effect}, true_driver=driver,
                 severity="HIGH" if kind != "planned" else "LOW")
            for i, kind, offset, duration, country, device, channel, category, driver, metric, effect in definitions]


def generate(months: int = 24, seed: int = 42, end: str = "2026-08-31") -> tuple[dict, list[dict]]:
    """Return source frames and a separate hidden registry. IDs are reproducible."""
    if not 12 <= months <= 60:
        raise ValueError("Generate between 12 and 60 months")
    rng = np.random.default_rng(seed)
    finish = pd.Timestamp(end).to_pydatetime().replace(hour=14, minute=5)
    dates = pd.date_range(pd.Timestamp(finish) - pd.DateOffset(months=months) + pd.Timedelta(days=1), finish)
    truth = scenario_registry(finish)
    names = ["customers", "products", "web_sessions", "orders", "payments", "refunds",
             "marketing_campaigns", "support_tickets", "subscriptions", "application_events",
             "deployments", "operational_incidents"]
    data = {name: [] for name in names}
    for ci, country in enumerate(COUNTRIES):
        for customer in range(30000):
            data["customers"].append(dict(id=f"c{ci}-{customer}", country=country,
                customer_segment=SEGMENTS[customer % 3], acquired_at=dates[0].to_pydatetime()))
    for pi, category in enumerate(CATEGORIES):
        data["products"].append(dict(id=f"p{pi}", product_category=category,
                                    price=[89., 69., 119.][pi], unit_cost=[23., 35., 20.][pi]))
    seen = set()
    active = np.full(126, 120, dtype=int)
    combinations = list(product(range(6), range(3), range(7)))
    for day_index, stamp in enumerate(dates):
        time = stamp.to_pydatetime()
        events = {r["true_driver"] for r in truth if r["start_time"] <= time <= r["end_time"]}
        seasonal = 1 + .12*np.sin(2*np.pi*stamp.dayofyear/365.25)
        weekday = [1.05, 1.02, 1.0, 1.03, 1.10, .88, .82][stamp.weekday()]
        trend = 1 + .15*day_index/len(dates)
        for k, (ci, di, ch) in enumerate(combinations):
            country, device, channel = COUNTRIES[ci], DEVICES[di], CHANNELS[ch]
            category = CATEGORIES[(ci + di + ch) % 3]
            pi = CATEGORIES.index(category)
            cohort = f"s{stamp:%Y%m%d}-{k}"
            promoted = "promotion" in events and channel == "Email"
            inefficient = "campaign_efficiency" in events and channel == "Paid Social"
            base = (600 if ci == 0 and di == 1 else 70) * (1.1 if ch in (0, 4) else 1)
            spend = base*.24*(1 if "Paid" in channel else .08)*trend
            spend *= 2.8 if inefficient else 1
            # Efficient spend contributes to traffic; inefficient campaign spends without incremental reach.
            traffic = int(rng.poisson((base + spend*.4/(2.8 if inefficient else 1))*seasonal*weekday*trend
                                     * (1.7 if promoted else 1)))
            checkout = "deployment" in events and ci == 0 and di == 1
            stockout = "inventory" in events and category == "Accessories"
            provider = "payment_provider" in events
            support = "support" in events and country == "France"
            intent_rate = .055 * (1.10 if channel in ("Email", "Direct") else 1) * (.45 if stockout else 1)
            attempts = int(rng.binomial(traffic, intent_rate))
            fail_rate = .66 if checkout else .32 if provider else .03
            failed = int(rng.binomial(attempts, fail_rate))
            paid = attempts-failed
            data["web_sessions"].append(dict(id=cohort, timestamp=time, country=country, device=device,
                channel=channel, product_category=category, customer_segment=SEGMENTS[(ci+ch)%3],
                sessions=int(traffic*.2) if "tracking" in events else traffic,
                server_sessions=traffic, planned_promotion=int(promoted)))
            data["marketing_campaigns"].append(dict(id=cohort, cohort_id=cohort,
                campaign=f"{channel}-{country}", spend=round(spend, 2)))
            tickets = int(rng.poisson(max(1, paid*.08)*(5 if support else 1)))
            churn_p = .014 if support and time >= truth[3]["start_time"]+timedelta(days=7) else .001
            churn = int(rng.binomial(active[k], churn_p))
            new = int(rng.binomial(paid, .035))
            data["subscriptions"].append(dict(id=cohort, cohort_id=cohort, active_start=int(active[k]),
                                               churned=churn, new_subscriptions=new))
            active[k] += new-churn
            data["support_tickets"].append(dict(id=cohort, cohort_id=cohort, tickets=tickets,
                csat=float(np.clip(rng.normal(2.1 if support else 4.3, .12), 1, 5))))
            data["application_events"].append(dict(id=cohort, cohort_id=cohort, checkout_errors=failed if checkout else 0,
                attempts=attempts, latency_ms=float(1800 if checkout or provider else 210)))
            customer_choices = rng.integers(0, min(10000, 100 + (day_index+1)*12), attempts)*3 + (ci+ch)%3
            amounts = np.round(np.array([89., 69., 119.])[pi]*rng.lognormal(0, .12, attempts), 2)
            for j in range(attempts):
                oid = f"o{stamp:%Y%m%d}-{k}-{j}"
                customer = f"c{ci}-{customer_choices[j]}"
                status = "FAILED" if j < failed else "PAID"
                is_new = int(customer not in seen and status == "PAID")
                if status == "PAID":
                    seen.add(customer)
                data["orders"].append(dict(id=oid, cohort_id=cohort, customer_id=customer, product_id=f"p{pi}",
                    timestamp=time, amount=float(amounts[j]), cost=[23., 35., 20.][pi], status=status, is_new=is_new))
                data["payments"].append(dict(id=oid, order_id=oid, provider="PayBridge" if provider else "EuroPay",
                    status=status, amount=float(amounts[j])))
                if status == "PAID" and rng.random() < (.08 if support else .025):
                    data["refunds"].append(dict(id=oid, order_id=oid, timestamp=time, amount=float(amounts[j])))
    deployment = truth[0]["start_time"] - timedelta(minutes=17)
    data["deployments"].append(dict(id="release-checkout-v2", timestamp=deployment, country="Germany",
                                    device="Mobile", release="checkout-v2", component="checkout"))
    for r in truth:
        if r["true_driver"] in ("inventory", "payment_provider", "support"):
            data["operational_incidents"].append(dict(id=r["id"], timestamp=r["start_time"],
                country=r["affected_country"], component=r["true_driver"],
                description=f"Operational signal: {r['true_driver']}", status="OPEN"))
    return {name: pd.DataFrame(rows) for name, rows in data.items()}, truth
