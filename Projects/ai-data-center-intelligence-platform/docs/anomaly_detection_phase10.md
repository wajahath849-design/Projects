# Phase 10: Explainable Anomaly Detection

## Outcome

The project now evaluates 242,664 facility-level observations across all twelve requested operational metrics and stores 893 explainable anomalies in `detected_anomalies`.

Supported metrics are PUE, power draw, cooling power, cooling cost, CPU, memory, disk, network utilization, latency, packet loss, downtime, and incident count. A supported metric can correctly produce zero anomaly rows when every observation remains inside its learned bounds; disk utilization did so in the accepted dataset.

## Method comparison

| Method | Anomalies | Rate |
|---|---:|---:|
| Global z-score, 3σ | 341 | 0.1405% |
| Global IQR, Tukey fences | 683 | 0.2815% |
| Seasonal IQR, Tukey fences | 893 | 0.3680% |

The governed method is `seasonal_iqr`. For each facility and calendar month it calculates the historical median, first quartile, third quartile, and the 1.5-IQR Tukey fences. This was selected because it is robust to extreme values, incorporates recurring calendar seasonality, has no opaque learned parameters, and can be explained row by row. Selection is a governance decision, not a claim that the method with the largest output count is automatically best.

## Observation grain

- Energy and network metrics: facility-day observations from canonical daily tables.
- Server metrics: facility-day averages computed from the canonical server measurements; `source_record_count` preserves how many server records contributed.
- Downtime and incident count: complete facility-month series, including zero-incident months.

The detector never fabricates a source measurement. It records the observed value, seasonal median, lower and upper bound, direction, robust anomaly score, severity, source table, grain, and contributing record count.

## Severity

Severity is deterministic and based on robust distance from the seasonal median:

- medium: outside the Tukey fence and below four robust standard deviations;
- high: at least four and below six;
- critical: at least six.

The accepted output contains 744 medium, 114 high, and 35 critical observations. Severity indicates statistical unusualness, not guaranteed operational impact.

## Reproduce

```powershell
python scripts\detect_anomalies.py
python -m pytest tests\test_anomaly_detection.py -q
```

The command writes `data/processed/detected_anomalies.csv`, refreshes the SQLite table transactionally, and records the comparison in `evaluation/results/anomaly_detection_phase10.json`.

## Limitations

- The accepted detector uses the complete 2015–2025 synthetic history as an offline baseline; production streaming detection should use only prior observations.
- Facility-day server averages can hide a single unhealthy server. Component risk in Phase 15 uses server-level evidence separately.
- An anomaly is a triage signal, not a root-cause conclusion.
- Statistical thresholds require operational calibration before real alerts or automation.

## Interview explanation

The detector deliberately starts with a robust statistical rule instead of opaque machine learning. The table makes every flag auditable, the audit compares alternative simple methods, and the design cleanly separates unusual behavior from causal diagnosis.
