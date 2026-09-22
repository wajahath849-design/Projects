# Demo data dictionary

| Column | Type | Definition | Audit role |
|---|---|---|---|
| `date` | date | Start of the observation period | Time comparison |
| `device` | category | Desktop or mobile experience | Primary segment |
| `region` | category | Commercial region | Additional dimension; recorded but not analyzed in the demo |
| `sessions` | integer | Eligible checkout sessions | Metric denominator |
| `conversions` | integer | Completed checkout sessions | Metric numerator |
| `revenue` | decimal | Revenue attributed to conversions | Context only |
| `release` | category | Checkout version active in the period | Context only |

This is synthetic data, not evidence from a real checkout experiment. The sample intentionally contains a Simpson's-paradox pattern. Conversion declines within desktop and mobile while the aggregate improves because a much larger share of traffic moves to desktop, the higher-converting segment.

The comparison begins on March 2, 2026. The primary analysis uses `device`; `region`, `revenue` and `release` supply context. The bundled offline report is a saved sample for exploring the interface. With the analysis service running, the demo is recalculated by the backend.
