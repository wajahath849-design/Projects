# Phase H — Correlation, Intervention, and Impact

The impact engine separates four evidence levels: ordinary correlation,
lead/lag temporal association, descriptive incident impact, and guarded
quasi-experimental intervention estimates. Correlations include sample size,
scope, time window, coefficient, and a Fisher 95% interval where applicable.
Lead/lag results state their direction convention.

Incident impact compares the seven days before, incident day, and seven days
after across power, PUE, latency, packet loss, and availability. It adds incident
duration, affected-server count, recovery timing, and modeled excess energy,
cost, and carbon where the governed assumptions resolve.

Difference-in-differences is allowed only with at least 14 paired pre-period
observations and correlation of 0.70 or higher. Interrupted time-series
association needs at least 30 observations on both sides. Otherwise the engine
falls back to descriptive comparison. The evidence score reports completeness,
temporal order, comparison design, pre-trend support, and confounder coverage;
it is explicitly not a probability. None of these paths uses causal wording.
