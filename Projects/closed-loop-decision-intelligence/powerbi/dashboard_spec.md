# Nine-page report specification

Use a restrained 16:9 layout: dark navy text, pale backgrounds, teal actuals, dashed
gray baselines, amber warnings and red critical failures. Severity must also appear
as text. Show the source watermark, synthetic-data label and active filters on every
page. No chatbot, decorative gauges, or untraceable generated explanations.

| Page | Primary visuals | Interaction and validation |
|---|---|---|
| 1 Executive Intelligence | Revenue, orders, conversion, AOV, CAC, churn; critical-incident list; selected-incident risk | Country/device/date filters; revenue reconciles to paid orders; show EUR gross/net labels |
| 2 KPI Observatory | Actual vs prior-weekday baseline; variance; country-device matrix | Single metric and grain; never combine all-scope and segment observations |
| 3 Anomaly Command Center | Time/severity table, metric timeline, alert score and quality class | Drillthrough to incident; tracking issues clearly distinguished from business incidents |
| 4 Automated Investigation | Contribution bars, signed delta waterfall, hypothesis text, evidence table, deployment timeline | One incident and one decomposition at a time; shares across dimensions are not additive |
| 5 Forecast & Risk | Daily forecast with shaded bounds, 7/30-day exposure | One incident; expose training cutoff, method, and persistence assumption |
| 6 Decision Center | Recommendations, heuristic confidence, expected effect, risk, approval status | Open FastAPI review separately; BI is read-only and must not imply approval on selection |
| 7 Decision Impact | Expected vs measured relative effect, interval, outcomes, complete ledger drillthrough | Pair pre/post windows with control; show simulation method and unsupported impact models |
| 8 Data Quality & Pipeline Health | Latest check results, failed records, tracking dates, stage runs | Warning is distinct from quarantine; one latest check execution per dataset |
| 9 Automation Performance | Stage success rate, decision/action/verification durations, approval/success rates | Use operational KPI endpoint/export and evaluation report; distinguish wall-clock processing from simulation dates |

The default demo story is Germany → Mobile → checkout-v2. Use the actual stored
numbers from `data/exports/demo_ledger.json`; never paste example outcomes into charts.
The comparison chart should show seven degraded pre-action days and seven explicitly
simulated post-action days, with Germany Desktop as the control.

Screenshots to capture after manual implementation: executive page, tracking warning,
Germany Mobile investigation, human approval, and completed Decision Ledger. Place
them under `docs/screenshots/`. No screenshots are supplied or claimed as rendered.
