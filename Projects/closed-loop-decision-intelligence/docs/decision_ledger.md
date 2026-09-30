# Decision Ledger and memory

`decision.v_decision_ledger` joins the entire decision chain with left joins, so
pending, rejected, and unmeasured decisions remain visible. It contains one row per
incident because hypothesis, recommendation, approval, action, impact, outcome and
lesson keys are unique at their declared grain. Evidence is a child collection;
`evidence_count` avoids multiplying ledger rows by every contribution record.

Lifecycle: incident → evidence → hypothesis → recommendation → approval → action →
expected impact → actual impact → outcome → lesson. Evidence IDs on the
recommendation resolve to stored numerical records. The hypothesis explicitly calls
the driver likely, never proven. Calculations and decisions use versioned statistical
methods and configured rules.

Approval is a guarded state machine: PENDING, APPROVED, REJECTED, EXPIRED. Human
endpoints require both the ordinary API token and a separate approval token. The
actor field is an asserted name in this local demo, not a verified enterprise identity.
Approvals expire after 24 hours, including approved actions not yet executed. Terminal
states cannot be reversed. Repeated accepted requests return the original result.

Action state is persisted once per recommendation. A row lock on the approval and a
unique key serialize concurrent PostgreSQL delivery. The local simulator has no
external side effect. For a real adapter, the database transaction alone cannot make
remote execution exactly-once: add an outbox and a receiver idempotency contract.

## Measuring the demo action

The rollback's policy target is **+100% relative treated conversion**, not 100
percentage points and not a predicted uplift from a trained causal model. The target
is deliberately explicit in `config/decision_rules.yaml` and stored before action.

The simulator replays the seven preceding weekdays into seven new post-action days.
Germany Mobile payments use a healthy 3% failure probability after the rollback;
Germany Desktop is the unchanged control. Existing historical observations are never
rewritten. Orders, payments and source cohorts remain linked. This is a deterministic
mechanism demonstration, not an independent experimental validation of rollback.

Daily paid-order/session conversion is compared across aligned seven-day pre/post
windows. Scaled difference in differences adjusts for the control change. A paired
day-block bootstrap produces a 95% interval. The implementation requires finite,
positive baselines and all seven days in all four windows; otherwise it waits or
refuses the calculation. It never treats missing post-action data as zero impact.

Outcomes: negative interval → NEGATIVE; interval spanning zero → INCONCLUSIVE
(or NO_EFFECT when entirely within ±2%); positive effect at least 80% of the policy
target → SUCCESS; other positive effects → PARTIAL_SUCCESS. The code also documents
parallel-trend and no-spillover assumptions. Seven days provide limited statistical
evidence, and the paired replay makes the synthetic control unusually stable.

Memory uses metric, dimension name/value and hypothesized driver. It returns only
closed incidents that predate the current incident and were closed before its
processing-time creation. Returned context includes actual measured outcomes, not
only recommendations. Memory is attached to a recommendation for review; it cannot
bypass approval or automatically change rule thresholds.

`GET /operations/kpis` reports processing-clock durations. Simulation dates and
wall-clock processing dates must not be subtracted to invent detection latency.
Minute-level MTTD and EUR revenue protected are unavailable rather than fabricated.
