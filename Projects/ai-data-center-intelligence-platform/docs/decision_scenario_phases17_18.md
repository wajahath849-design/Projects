# Phases 17–18: Decision Support and Scenario Analysis

## Efficiency-upgrade prioritization

`FacilityDecisionSupport` ranks all facilities from a fixed burden model:

| Indicator | Weight |
|---|---:|
| Latest average PUE | 25% |
| Latest cooling cost | 20% |
| Downtime per server | 15% |
| Incident rate per 100 servers | 10% |
| Historical PUE trend | 10% |
| Anomaly count | 10% |
| Five-year PUE projection | 10% |

Each burden is normalized across peer facilities and its weighted contribution remains visible in the ranking. The model reports the top candidate, three largest supporting contributions, the lead over the next facility, and deterministic decision confidence. Weights are versioned in `analytics/decision_support_weights.yaml`; the LLM cannot modify them.

This feature prioritizes human review. It does not approve spending, maintenance, or configuration changes.

## What-if scenarios

`ScenarioEngine` supports PUE, cooling power, cooling cost, CPU, memory, disk, latency, and packet-loss scenarios. The caller supplies a percentage assumption and optional facility and baseline year.

Every output explicitly labels:

- `historical_fact` or `forecast` baseline;
- user-supplied percentage assumption;
- calculated scenario value;
- calculated difference;
- metric unit and facility.

A future baseline uses the existing governed forecast engine first, then applies the scenario assumption. The result remains labelled a scenario and is never presented as a new forecast or observed outcome. Percentage metrics are bounded to 0–100 and PUE to its governed 1–2 range; extreme assumptions are rejected.

## Examples

```text
PUE improves 10%
=> change_pct = -10
=> historical or forecast baseline × 0.90

CPU demand increases 20%
=> change_pct = +20
=> baseline × 1.20, capped at 100%

Cooling efficiency improves 15%
=> cooling power or cooling cost change_pct = -15
=> baseline × 0.85
```

## Validation status

Tests cover ranked weights, decision caveats, historical and future baselines, bounded metrics, metric-aware improvement direction, scenario labels, and rejected extreme inputs. They pass in the accepted full regression suite.

## Interview explanation

Forecasting estimates what may happen from history. Scenario analysis calculates what would happen under an explicit assumption. Decision support combines governed evidence to prioritize human attention. Keeping these three products separate prevents a plausible-looking number from being mistaken for a fact or an approved decision.
