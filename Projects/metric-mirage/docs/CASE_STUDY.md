# Portfolio case study

## The problem

Business dashboards answer “what moved?” but frequently fail to answer “can we trust the explanation?” Aggregation, changing customer mix and instrumentation problems can turn a numerically correct KPI into a poor decision.

## The product

Metric Mirage combines a business claim and its supporting dataset in a structured review. It compares a ratio across two periods, tests assumptions with deterministic checks and produces an evidence report that a manager can inspect without reading a notebook. Claim text supplies context; the engine does not interpret free-text causality.

## Demonstration story

In a synthetic demonstration, a company launches a new checkout and observes a large aggregate conversion increase. The platform discovers that:

1. Desktop and mobile conversion both declined.
2. Traffic composition shifted heavily toward desktop.
3. Holding the old device mix constant reverses the apparent improvement.
4. The release cannot responsibly be credited for the aggregate increase.

## Engineering decisions

- A pure Python analysis boundary keeps statistical logic independently testable.
- Structured findings connect each explanation to calculated evidence; no language model is used.
- A one-shot anonymous endpoint supports CSV reviews. The frontend keeps results for the current session, while separate authenticated API resources support persistence.
- SQLite supports zero-configuration local development while PostgreSQL is the containerized default.
- SVG and CSS visualizations keep the bundle small and make the crucial paradox visually explicit.
- Unsupported checks are displayed as not assessed; the evidence score is identified as a heuristic and presented alongside coverage.
- JSON downloads preserve the full calculation record; the printable decision report provides a shorter reading format.

## Future work

- Difference-in-differences and interrupted time-series checks.
- Metric-definition version history and SQL lineage.
- Warehouse connectors and scheduled monitoring.
- Multiple-comparison controls for exploratory segment discovery.
- Asynchronous analysis for larger datasets.
- Authenticated frontend history and owner-scoped persistent resources.
