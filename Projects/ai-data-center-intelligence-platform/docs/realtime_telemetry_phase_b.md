# Phase B — Real-Time Telemetry Foundation

## Outcome

The project now has an isolated, bounded real-time telemetry path. The canonical
2015–2025 SQLite database remains read-only during application use. Synthetic events
are stored in `database/realtime.db` with explicit simulation provenance.

## Architecture

```text
Canonical history (read-only) -> baseline profiles -> telemetry simulator
                                                    -> bounded queue
                                                    -> validation
                                                    -> real-time SQLite store
```

The local queue and SQLite design is intentional. It supports a reproducible portfolio
demonstration without introducing an unnecessary distributed streaming platform.

## Event coverage

- Server: CPU, memory, disk, network utilization, simulated temperature and status.
- Facility: IT load, cooling power, total power, PUE and interval energy.
- Network: utilization, latency, throughput, loss and availability.
- Reliability: availability, downtime, alert count and incident indicator.
- Operational events: typed logs, alerts and incident lifecycle events.

All event timestamps are timezone-aware UTC values. Numeric values must be finite,
use the governed unit for their metric and stay inside defensive physical bounds.
Facility and server identifiers are verified against canonical inventory.

## Energy meaning

`energy_consumption_kwh` is calculated for each simulator interval as:

`power_draw_kw * tick_interval_seconds / 3600`

It is a synthetic interval calculation, not a claim of metered production energy.
No electricity price is applied in this phase.

## Retention and safety

Each session has a retention period and maximum event count. Cleanup affects only
records belonging to that simulation session. It never reads, updates or deletes
historical canonical records. The AI and Text-to-SQL paths do not receive a write
connection to the real-time database.

## Running a controlled sample

`python scripts/run_telemetry_simulator.py --ticks 12 --speed 10`

The command creates a new synthetic session and stops after the requested number of
ticks. Continuous UI controls and incident injection belong to Phase D.

Use `--ticks 0` for a continuous run that stops cleanly with Ctrl+C. The command now
passes every batch through streaming analytics, so rolling state, anomalies and live
health remain synchronized with stored events.

## Limitation

This is a local simulation system. It is not connected to physical infrastructure and
cannot perform operational control.

## Validation result

- Phase B focused tests: 5 passed.
- Phase B full regression checkpoint: 167 passed in 405.82 seconds.
- Canonical database content was hash-checked before and after simulation writes.
- The real-time database passed integrity and foreign-key checks.
