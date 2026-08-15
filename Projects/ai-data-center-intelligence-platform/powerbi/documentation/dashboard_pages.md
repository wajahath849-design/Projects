# Power BI Foundation Pages

This is the final source specification for the three report pages. Apply `powerbi/theme/DataCenterExecutive.json`; the PBIP generator and tests preserve page/model metadata. Final pixel-level review and `.pbix` export require Power BI Desktop.

## Page 1 — Executive Operations Overview

Hero cards: Average PUE, Total Downtime, Operational Availability, Incident Count, Active Server Count, Total Cooling Cost, Average CPU Utilization, Network Availability.

Foundation visuals:

- Average PUE by facility: clustered bar.
- Total downtime by facility: bar.
- Incident count by month: line.
- Total power draw by month: line.
- Facility comparison: matrix with PUE, downtime, incident rate, network availability, and cooling cost.

Global slicers: date, facility, region.

## Page 2 — Infrastructure Performance

Hero cards: Average CPU, memory, disk, server-network utilization, latency, packet loss, throughput, active servers.

Foundation visuals:

- CPU and memory trend by month.
- Utilization distribution by server type.
- Server status composition.
- Network latency and packet loss by facility.
- High-utilization server detail table.

## Page 3 — Energy & Reliability

Hero cards: Average PUE, total power draw, cooling power, cooling cost, total downtime, incident count, operational availability.

Foundation visuals:

- PUE yearly trend with YoY change.
- Cooling cost yearly trend.
- Downtime and incident trend.
- Root-cause breakdown.
- Facility reliability comparison.

## Interaction rules

- Slicers filter all visuals on their page.
- Facility and date slicers synchronize across pages.
- Charts cross-filter; avoid bidirectional model relationships.
- Tooltips show exact value, period, facility, and relevant denominator.
- Latest date is 31 Dec 2025; relative-period language anchors to loaded data, not the current date.
