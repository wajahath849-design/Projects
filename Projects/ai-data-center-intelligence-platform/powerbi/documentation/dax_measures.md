# Foundational DAX Measures

The complete copy-ready definitions are in `powerbi/foundation/DAX/measures.dax`.

## Filter-context rules

Measures recalculate under active date, facility, region, server, severity, and root-cause filters. They are measures rather than calculated columns because their results must change with report context and should not store a repeated aggregate on every row.

## Metric explanations

| Measure | Meaning | Format | Validation |
|---|---|---|---|
| Average PUE | arithmetic mean of visible daily PUE rows | 0.000 | SQL/Python overall value 1.476205 |
| Total Power Draw | sum of daily power-draw observations | #,##0.00 | 118,172,953.04 overall |
| Total Cooling Cost | sum of synthetic cooling cost | #,##0.00 | 102,313,662.66 overall |
| Total Downtime | incident downtime minutes | #,##0 | 73,559 overall |
| Incident Count | distinct incident IDs | #,##0 | 1,158 overall |
| Server Count | distinct visible servers | #,##0 | 430 overall |
| Active Server Count | visible servers with active status | #,##0 | 407 overall |
| Average CPU Utilization | mean visible daily CPU percentage | 0.00% displayed on 0–100 scale without multiplying | 48.743428 overall |
| Average Memory Utilization | mean visible daily memory percentage | 0.00 | 48.120738 overall |
| Average Network Latency | mean visible latency | 0.00 ms | 10.896964 overall |
| Average Packet Loss | mean visible packet-loss percentage | 0.000 | 0.056492 overall |
| Network Availability | mean measured availability | 0.0000 | 99.961103 overall |
| Downtime per Server | downtime divided by visible servers | 0.00 | 171.067442 overall |
| Incident Rate per 100 Servers | incidents divided by servers × 100 | 0.00 | 269.302326 overall over 11 years |
| Operational Availability | potential server-minutes not recorded as downtime | 0.0000 | 99.997043 overall |
| Log Count | distinct operational log events | #,##0 | 5,790 current synthetic evidence rows |
| Critical Alert Count | distinct critical alerts | #,##0 | reconciles to `alerts` under filters |
| Anomaly Count | distinct governed anomaly rows | #,##0 | 893 accepted Phase 10 rows |
| Maintenance Action Count | distinct recorded actions | #,##0 | 1,158 current rows |
| MTTR Minutes | mean recorded incident downtime | 0.00 | uses the same incident duration field as AI |
| Average Server Risk Score | mean visible explainable risk score | 0.00 | versioned seven-day screening snapshot |
| High Risk Server Count | distinct high or critical risk servers | #,##0 | fixed score bands |
| Average Facility Health Score | mean visible governed health score | 0.00 | fixed versioned weights |
| Modeled Energy Cost | monthly modeled energy cost from governed price assumptions | USD | synthetic assumption snapshot |
| Modeled Cooling Cost | modeled cooling share of energy cost | USD | reconciles to modeled cooling energy × price |
| Modeled Carbon | modeled location-based carbon estimate | tonnes CO2e | synthetic intensity snapshot |
| Average Efficiency Opportunity Score | weighted cross-facility opportunity index | 0–100 | versioned weights, not a performance target |
| Incident Impact Count | incidents represented in the descriptive impact snapshot | #,##0 | one row per canonical incident |
| Average Incident PUE Change | seven-day after versus before change | percentage points shown numerically | descriptive association only |
| Average Incident Latency Change | seven-day after versus before change | percentage points shown numerically | descriptive association only |
| Modeled Downtime Cost Exposure | time-proportional modeled energy-cost exposure | USD | not a causal loss estimate |
| Live Facility Health Score | latest bounded simulation health score | 0–100 | isolated simulation snapshot |

Do not use Power BI's percentage format directly for values stored on a 0–100 scale; it multiplies by 100. Use a numeric format with a literal percent sign when desired, such as `0.00\%`.

## Year-over-year measures

Each YoY measure uses `DATEADD(DimDate[Date], -1, YEAR)` and divides the difference by the prior-year value. This requires a contiguous marked date table and active date-to-fact relationships.

Validated 2025-versus-2024 results:

- PUE change: -1.030164%.
- Cooling cost change: +0.235301%.
- Downtime change: +34.494510%.

These are measured historical comparisons, not targets or forecasts.
