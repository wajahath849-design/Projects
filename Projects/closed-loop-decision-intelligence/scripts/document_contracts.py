"""Publish data/metric dictionaries from executable contracts."""
from src.common.config import ROOT
from src.common.models import metadata
from src.metrics.engine import registry


def document():
    folder = ROOT / "docs"
    folder.mkdir(exist_ok=True)
    lines = ["# Data dictionary", "", "Generated from `src/common/models.py`. All records are synthetic.", "",
             "Orders/payments/refunds are transactions. Sessions, campaigns, support, subscriptions and",
             "application events are daily country-device-channel cohort summaries. Product category and",
             "customer segment are cohort attributes. Customers are a registered pool; new customers means",
             "first observed purchasers. Amounts are EUR; naive timestamps represent UTC.",
             "Simulation dates label source time; created_at/updated_at label processing time.", ""]
    for table in metadata.sorted_tables:
        lines += [f"## {table.fullname}", "", "| Column | Type | Nullable | Reference |", "|---|---|---|---|"]
        for column in table.columns:
            reference = ", ".join(f.target_fullname for f in column.foreign_keys) or ("Primary key" if column.primary_key else "")
            lines.append(f"| {column.name} | {column.type} | {column.nullable} | {reference} |")
        lines.append("")
    (folder / "data_dictionary.md").write_text("\n".join(lines), encoding="utf-8")
    lines = ["# Metric dictionary", "", "Source: config/metrics.yaml and validated Metric defaults.", "",
             "Ratios use summed components. Zero denominators yield missing values. Active Customers uses",
             "distinct paying customer IDs at the selected grain, not a sum of cohort distinct counts.", "",
             "| Metric | Definition | Owner | Adverse direction | Aggregation |", "|---|---|---|---|---|"]
    for metric in registry():
        lines.append(f"| {metric.metric_id} | {metric.description} | {metric.owner} | {'Decrease' if metric.direction == 'up' else 'Increase'} | {metric.aggregation} |")
    lines += ["", "Defaults: daily monitoring; country/device/channel/product_category/customer_segment dimensions;",
              "20% warning, 40% critical deviation; trailing same-weekday comparison. Thresholds are votes,",
              "not standalone alert triggers. The ensemble and incident scope rules also apply.", "",
              "Hourly grouping is supported but this generator supplies daily snapshots, not intraday history.",
              "Churn and retention use subscriber-days, not cohort retention. Gross margin excludes refunds",
              "and tax. ROAS is attributed revenue per allocated spend, not incremental marketing ROI."]
    (folder / "metric_dictionary.md").write_text("\n".join(lines)+"\n", encoding="utf-8")


if __name__ == "__main__":
    document()
