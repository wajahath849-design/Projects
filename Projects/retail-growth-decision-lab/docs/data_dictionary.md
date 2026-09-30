# Data dictionary

## Currency conventions

The source ledger, original commercial outputs, and model-training features use GBP. Files under `data/processed/eur/`, `models/candidates_eur.csv`, and the dashboard use EUR translated at historical transaction-date ECB reference rates. EUR campaign exports explicitly carry a `currency` column. See [currency methodology](currency_methodology.md) for quote direction, holiday handling, value caps, and reconciliation.

## Core analytical tables

| Table/file | Grain | Key fields |
|---|---|---|
| `line_items` in `data/retail.sqlite` | Audited unique source line | invoice, product, timestamp, customer, classification, exclusion reason, line revenue |
| `data/processed/orders.csv` | Valid positive invoice × customer | customer, invoice, timestamp, country, revenue, quantity |
| `data/processed/monthly.csv` | Complete calendar month | gross sales, returns value, net sales, orders, customers, MoM growth, customer mix |
| `data/processed/cohorts.csv` | Cohort × mature age month | retained customers, cohort size, retention |
| `data/processed/countries.csv` | Country | gross sales, orders, identified customers |
| `models/candidates.csv` | Known customer at 1 Nov 2011 | behavioral features, calibrated probability, capped order value, priority score |

## Key definitions

| Field | Definition |
|---|---|
| `gross_sales` | Sum of positive valid catalogue-merchandise line value |
| `returns_value` | Absolute value of negative valid catalogue-merchandise lines on their recorded dates |
| `net_sales` | Gross sales minus returns value; not accounting revenue or profit |
| `identified_sales_share` | Gross sales with a valid customer ID divided by all gross sales |
| `retention` | Purchasing cohort members divided by original cohort size at a mature age month |
| `purchase_probability` | Calibrated probability of a positive purchase in the next 30 days |
| `priority_score` | Capped historical order value × (1 − purchase probability); non-causal heuristic |
