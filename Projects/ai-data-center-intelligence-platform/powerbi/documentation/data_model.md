# Power BI Foundation Data Model

## Purpose

The Power BI model is an analytical star schema, not a copy of SQLite's operational layout. It imports the verified `data/processed` CSVs because Power BI Desktop does not include a native SQLite connector and a third-party SQLite ODBC driver is not assumed.

The AI layer uses the equivalent SQLite tables. Shared contracts and KPI definitions keep both consumer layers aligned.

## Tables

| Power BI table | Source | Role | Grain |
|---|---|---|---|
| DimDate | calculated DAX table | conformed date dimension | one date |
| DimFacility | facilities.csv | dimension | one facility |
| DimServer | servers.csv | dimension | one server |
| FactServerMetrics | server_metrics.csv | fact | server per day |
| FactPowerMetrics | power_metrics.csv | fact | facility per day |
| FactNetworkMetrics | network_metrics.csv | fact | facility per day |
| FactIncidents | uptime_incidents.csv | fact | incident |
| _Measures | empty home table | measure organization | not applicable |

## Relationships

| From (one) | To (many) | Active | Direction | Reason |
|---|---|---|---|---|
| DimFacility[facility_id] | DimServer[facility_id] | yes | single | facility filters server inventory |
| DimFacility[facility_id] | FactPowerMetrics[facility_id] | yes | single | facility filters energy facts |
| DimFacility[facility_id] | FactNetworkMetrics[facility_id] | yes | single | facility filters network facts |
| DimFacility[facility_id] | FactIncidents[facility_id] | yes | single | facility filters reliability facts |
| DimServer[server_id] | FactServerMetrics[server_id] | yes | single | server filters utilization facts |
| DimServer[server_id] | FactIncidents[server_id] | no | single | inactive to avoid an ambiguous Facility→Server→Incident path |
| DimDate[Date] | FactServerMetrics[timestamp] | yes | single | conformed daily filtering |
| DimDate[Date] | FactPowerMetrics[timestamp] | yes | single | conformed daily filtering |
| DimDate[Date] | FactNetworkMetrics[timestamp] | yes | single | conformed daily filtering |
| DimDate[Date] | FactIncidents[incident_date] | yes | single | incident filtering by start date |

All filters flow from dimensions to facts. Bidirectional filtering is intentionally avoided because it can produce ambiguous propagation and unexpected totals.

## Fact versus dimension

A dimension describes entities used for filtering and grouping. A fact records measurable events at a declared grain. Dimensions sit on the `1` side of relationships; facts sit on the `*` side.

## Date table

DimDate contains all 4,018 days from 1 Jan 2015 through 31 Dec 2025. Mark `DimDate[Date]` as the model's date table and sort Month by Month Number. Disable Auto date/time for the file.

## Keys

The model uses stable business keys from the canonical data. Power BI does not need additional surrogate keys at this stage because the dimensions are Type 1 snapshots from one source. Surrogates may be introduced if future datasets require slowly changing dimension history or overlapping source identifiers.

## Import mode

Import mode is appropriate for a portable portfolio project with approximately 1.8M fact rows. It provides fast visual interactions without requiring a continuously running database. Refresh reads the same canonical processed files validated against SQLite.

