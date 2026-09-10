# Phase D — Incident Simulation and Replay

The local lab now provides six deterministic scenarios: cooling degradation,
network congestion, server overload, power instability, storage pressure, and a
combined cascading failure. Each run has an isolated session, a canonical
facility scope, explicit synthetic provenance, and operator controls for start,
pause, resume, reset, replay, and 1×/2×/5×/10× speed.

Only telemetry, logs, alerts, incidents, anomalies, and health changes are
available to runtime investigation services. Scenario evaluation truth remains
under `evaluation/private/`, which production modules never import or read.
Reset and replay affect only the selected real-time session; the historical
database is opened read-only and is never modified.
