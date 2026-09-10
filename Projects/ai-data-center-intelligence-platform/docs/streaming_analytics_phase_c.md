# Phase C — Streaming Analytics and Live Health

## Outcome

Incoming synthetic telemetry is converted into incremental operational state that can
answer current-state questions without scanning canonical history.

## Maintained state

- Latest facility and server metric values.
- One-, five- and fifteen-minute rolling mean, minimum, maximum and standard deviation.
- Per-minute change rate and deviation from the current rolling mean.
- Active anomalies and alerts.
- Deterministic live facility health with driver summaries.
- Event and state versions for safe cache invalidation.

If `event_version` is greater than `state_version`, a consumer knows that telemetry was
stored but streaming calculations have not yet caught up. Successfully processed state
always advances to the corresponding event version.

## Online anomalies

The online detector combines two transparent methods:

1. Governed operational thresholds for signals such as CPU saturation, high PUE,
   packet loss, temperature, availability and server status.
2. A rolling z-score when at least five prior valid observations are available.

Every anomaly records its triggering event, baseline sample count, mean, standard
deviation, threshold reference, observed value, expected value, deviation, severity,
method and simulation session. Statistical anomalies are associations with a baseline,
not root-cause conclusions.

## Live health

Live health is separate from the historical annual health score. The configured weights
cover energy efficiency, reliability, network health, infrastructure pressure, active
alerts and active anomalies. Drivers are calculated from component scores; the LLM does
not generate them.

The output includes data completeness so a partially observed facility is not presented
as if every operational dimension were available.

## Performance design

Only the bounded real-time window is scanned for rolling calculations. Current metrics,
health and active evidence are persisted as compact snapshots. Future Streamlit pages
can cache reads using `(simulation_session_id, state_version)` and invalidate them as
soon as processed telemetry changes.

## Limitations

This phase provides backend streaming analytics. Conversational routing is Phase I and
live Streamlit presentation is Phase J. The telemetry remains synthetic and cannot
control infrastructure.

## Validation result

- Phase B and C focused tests: 10 passed in 9.66 seconds.
- Complete project regression suite: 172 passed in 339.41 seconds.
- One end-to-end normal tick processed 192 events.
- That tick produced 576 rolling-state records and six facility health snapshots.
- The real-time database reported integrity `ok` and zero foreign-key violations.
- The normal-operation smoke run produced zero anomalies, as expected.
