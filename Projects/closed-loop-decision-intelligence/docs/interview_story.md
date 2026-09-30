# Interview story

## 30 seconds

I built a closed-loop analytics portfolio that follows a business signal beyond a
dashboard. It generates linked commerce data, validates it, detects anomalies,
investigates likely drivers, and proposes actions. A separate human approval gates
the simulated action. The Decision Ledger then records whether the measured outcome
matched the target. The distinction between detection and verification is the point.

## Two minutes

The fictional company sells across six European countries and seven acquisition
channels. I generated two years of correlated transactions and operational signals,
including checkout, provider, campaign, inventory, support and tracking incidents.
Ground truth is isolated from the analytical code and used only for evaluation.

n8n orchestrates separate FastAPI stages. PostgreSQL stores raw data, SQL/dbt marts,
monitoring results and decision history. Python implements prior-only seasonal
baselines, statistical ensemble detection, dimensional contributions and simple
forecasts. The tracking example is important: tracked sessions collapse while server
traffic and orders remain stable, so the system suppresses misleading conversion
alerts and recommends a tracking fix.

For the checkout demo, payment failures and a recent deployment support a rollback
hypothesis. An explicit approval authorizes only a local simulation. Seven new source
days are compared with the degraded week and a desktop control. The ledger stores
the policy target, measured effect, interval, outcome and lesson. Measured synthetic
results and limitations are published together, including false positives.

## Five minutes

Extend the two-minute explanation with the following evidence in order:

1. Show the quality gate and the independent tracking reconciliation. Explain why
   data reliability must precede business interpretation.
2. Show the SQL mart grain. Explain ratios of sums and distinct customer counts,
   foreign-key tests, and revenue reconciliation.
3. Show an anomaly's prior-only baseline, ensemble votes and scope. Explain that the
   score is a heuristic and that the first evaluation missed inventory at global scope.
4. Show contributions, signed deltas and the deployment timestamp. A recent deployment
   is evidence supporting a hypothesis, not proof of causation.
5. Show the recommendation, separate approval credential, idempotent action and
   WAITING_FOR_DATA path. No service token alone can authorize a human decision.
6. Show the completed ledger and the explicit replay assumptions. Finish with the
   evaluated false positives and which Docker/Power BI checks were not executed.

## Technical discussion and likely questions

**Why n8n? Why not Airflow?** n8n makes local webhooks, human handoffs, branching and
API orchestration visible in a demo. Airflow would be a reasonable choice for large
scheduled DAGs and backfills. Neither should contain the statistical implementation.

**Why Python outside n8n?** Versioned modules, unit tests, numerical libraries and
parameterized SQL are easier to review than calculations embedded in workflow nodes.

**How does detection work?** Static deviation thresholds, rolling z-score, robust MAD,
rolling median, EWMA, same-weekday baselines and an Isolation Forest vote. The forest
uses only initial history; rolling features exclude the current observation. Business
direction and quality gates filter candidate alerts. Scope policies govern incidents.

**How do you prevent false alerts?** Quality checks, scoped suppression, same-weekday
comparisons, adverse-direction filters and episode coalescing reduce noise. They do
not eliminate it. The evaluation reports precision, recall and the negative-day
denominator explicitly. Further calibration needs independent seeds and real data.

**How do you identify root causes?** I rank within-dimension revenue contributions,
check connected metrics, and inspect deployment and operational context. The result
is a structured hypothesis. Correlation and temporal proximity do not prove causation.

**How does impact verification work?** Complete aligned seven-day windows, a treatment
scope, an unaffected control assumption, scaled difference in differences and a
paired day bootstrap. Missing data produces a waiting state. The demo uses an explicit
replay intervention mechanism, so its success must not be presented as a real experiment.

**What makes the ledger different?** It retains pending and rejected decisions as well
as completed ones, and connects the original evidence and target to the actual outcome.
It provides an audit trail for whether a recommendation was useful, not just plausible.

**What would change in production?** Separate database roles; SSO and approver RBAC;
TLS and a secret manager; source contracts, CDC and watermarks; an outbox for actions;
external idempotency; backup/restore drills; drift monitoring; and independent causal
validation. Review the documented runtime gaps before claiming deployability.

**How would this scale? How would Kafka fit?** Partition event facts by event time,
incrementalize dbt, bound analytical jobs and move CPU work behind a queue. Kafka
could deliver versioned event contracts and replayable offsets. It would not replace
the warehouse, the approval state machine or effect measurement.

**How would cloud deployment work?** Managed PostgreSQL, container workers, private
networking, managed secrets, object-storage landing zones and centralized audit logs.
Choose services from actual availability and compliance requirements, not from this
local demo's Compose configuration.

**How would you secure the platform?** Separate the service and approval identities,
deny analytics access to hidden labels, restrict warehouse schemas, and audit state
transitions. A shared local approval token and an actor string are demo conveniences,
not enterprise identity verification.
