# Phases F–G — Governed Cost, Carbon, and Efficiency

Cost and carbon now use date-effective facility assumptions in
`data/assumptions/`. Every factor carries its currency or methodology, source
label, validity period, and synthetic status. The deterministic engine converts
each daily average-kW observation to modeled kWh using 24 hours, then calculates
energy/IT/cooling cost and carbon with explicit unit conversions.

The portfolio output includes facility totals, cooling share, cost per server,
cost per IT kWh, carbon by component, annual projections, efficiency scenarios,
savings, avoided emissions, and a versioned 0–100 relative opportunity score.
The score uses 40% PUE, 30% cooling cost per IT kWh, 20% carbon intensity, and
10% incident rate. It is a prioritization aid—not a safety rating, invoice,
audited inventory, or guaranteed financial return.
