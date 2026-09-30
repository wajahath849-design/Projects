"""Relational warehouse contracts shared by ingestion and analytics services.

Operational feeds have declared grains. Traffic, campaign, support and subscription
feeds are cohort snapshots; orders, payments and refunds are individual transactions.
"""
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()


def col(name, kind=String, **kwargs):
    return Column(name, kind, nullable=False, **kwargs)


def table(schema, name, *columns, constraints=()):
    return Table(name, metadata, col("id", String, primary_key=True), *columns,
                 Column("created_at", DateTime, nullable=False, server_default=func.now()),
                 Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
                 *constraints, schema=schema)


customers = table("raw", "customers", col("country"), col("customer_segment"), col("acquired_at", DateTime))
products = table("raw", "products", col("product_category"), col("price", Float), col("unit_cost", Float),
                 constraints=(CheckConstraint("price >= unit_cost AND unit_cost >= 0"),))
web_sessions = table("raw", "web_sessions", col("timestamp", DateTime), col("country"), col("device"),
                     col("channel"), col("product_category"), col("customer_segment"),
                     col("sessions", Integer), col("server_sessions", Integer), col("planned_promotion", Integer),
                     constraints=(CheckConstraint("sessions >= 0 AND server_sessions >= 0"),))
orders = table("raw", "orders", col("cohort_id", String, ),
               col("customer_id"), col("product_id"), col("timestamp", DateTime),
               col("amount", Float), col("cost", Float), col("status"), col("is_new", Integer),
               constraints=(ForeignKeyConstraint(
                   ["cohort_id"], ["raw.web_sessions.id"]),
                   ForeignKeyConstraint(["customer_id"], ["raw.customers.id"]),
                   ForeignKeyConstraint(["product_id"], ["raw.products.id"]),
                   CheckConstraint("amount >= 0 AND cost >= 0"),
                   CheckConstraint("status IN ('PAID','FAILED')")))
payments = table("raw", "payments", col("order_id"), col("provider"), col("status"), col("amount", Float),
                 constraints=(ForeignKeyConstraint(["order_id"], ["raw.orders.id"]),
                              UniqueConstraint("order_id"), CheckConstraint("status IN ('PAID','FAILED')")))
refunds = table("raw", "refunds", col("order_id"), col("timestamp", DateTime), col("amount", Float),
                constraints=(ForeignKeyConstraint(["order_id"], ["raw.orders.id"]),
                             CheckConstraint("amount > 0")))
marketing_campaigns = table("raw", "marketing_campaigns", col("cohort_id"), col("campaign"), col("spend", Float),
                            constraints=(ForeignKeyConstraint(["cohort_id"], ["raw.web_sessions.id"]),
                                         UniqueConstraint("cohort_id"), CheckConstraint("spend >= 0")))
support_tickets = table("raw", "support_tickets", col("cohort_id"), col("tickets", Integer), col("csat", Float),
                        constraints=(ForeignKeyConstraint(["cohort_id"], ["raw.web_sessions.id"]),
                                     UniqueConstraint("cohort_id"), CheckConstraint("csat BETWEEN 1 AND 5")))
subscriptions = table("raw", "subscriptions", col("cohort_id"), col("active_start", Integer),
                      col("churned", Integer), col("new_subscriptions", Integer),
                      constraints=(ForeignKeyConstraint(["cohort_id"], ["raw.web_sessions.id"]),
                                   UniqueConstraint("cohort_id"),
                                   CheckConstraint("churned BETWEEN 0 AND active_start")))
application_events = table("raw", "application_events", col("cohort_id"), col("checkout_errors", Integer),
                           col("attempts", Integer), col("latency_ms", Float),
                           constraints=(ForeignKeyConstraint(["cohort_id"], ["raw.web_sessions.id"]),
                                        UniqueConstraint("cohort_id")))
deployments = table("raw", "deployments", col("timestamp", DateTime), col("country"), col("device"),
                    col("release"), col("component"))
operational_incidents = table("raw", "operational_incidents", col("timestamp", DateTime), col("country"),
                             col("component"), col("description"), col("status"))
simulation_ground_truth = table("simulation", "simulation_ground_truth", col("incident_type"),
                               col("start_time", DateTime), col("end_time", DateTime), col("affected_country"),
                               col("affected_device"), col("affected_channel"), col("affected_product"),
                               col("expected_metric_effect", JSON), col("true_driver"), col("severity"))
pipeline_runs = table("monitoring", "pipeline_runs", col("workflow_name"), col("start_time", DateTime),
                      Column("end_time", DateTime), col("status"), col("rows_processed", Integer, default=0),
                      Column("error_message", Text))
data_quality_results = table("monitoring", "data_quality_results", col("run_id"), col("dataset"),
                             col("check_type"), col("status"), col("severity"), col("details", JSON),
                             Column("column_name", String), Column("expected_value", String),
                             Column("actual_value", String))
metric_observations = table("monitoring", "metric_observations", col("metric_id"), col("timestamp", DateTime),
                            col("dimension_name"), col("dimension_value"), Column("actual_value", Float),
                            Column("baseline_value", Float), Column("expected_value", Float),
                            Column("deviation_absolute", Float), Column("deviation_percent", Float),
                            col("grain"))
anomalies = table("monitoring", "anomalies", col("metric"), col("timestamp", DateTime),
                  col("dimension_name"), col("dimension_value"), col("actual", Float), col("expected", Float),
                  col("deviation", Float), col("method", JSON), col("anomaly_score", Float), col("severity"),
                  col("confidence", Float), col("data_quality_status"), col("classification"))
incidents = table("decision", "incidents", Column("anomaly_id", String, ForeignKey("monitoring.anomalies.id"), unique=True),
                  col("detected_at", DateTime), col("metric"), col("problem", Text), col("severity"),
                  col("dimension_name"), col("dimension_value"), col("driver", default="unknown"),
                  col("status", default="OPEN"), Column("closed_at", DateTime))
evidence = table("decision", "evidence", Column("incident_id", String, ForeignKey("decision.incidents.id"), nullable=False),
                 col("evidence_type"), col("dimension"), col("segment"), col("metric"),
                 col("current_value", Float), col("baseline_value", Float), col("difference", Float),
                 col("contribution", Float), col("statistical_strength", Float), col("description", Text))
hypotheses = table("decision", "hypotheses", Column("incident_id", String, ForeignKey("decision.incidents.id"), nullable=False),
                   col("driver"), col("description", Text), col("confidence", Float), col("signals", JSON))
forecasts = table("monitoring", "forecasts", Column("incident_id", String, ForeignKey("decision.incidents.id")),
                  col("metric"), col("timestamp", DateTime), col("horizon", Integer), col("expected", Float),
                  col("lower", Float), col("upper", Float), col("exposure", Float), col("method"))
recommendations = table("decision", "recommendations", Column("incident_id", String, ForeignKey("decision.incidents.id"), nullable=False, unique=True),
                        col("recommendation_type"), col("description", Text), col("supporting_evidence", JSON),
                        col("confidence", Float), col("expected_impact", Float), col("risk_level"),
                        col("requires_approval", Integer), col("memory_context", JSON))
approvals = table("decision", "approvals", Column("recommendation_id", String, ForeignKey("decision.recommendations.id"), nullable=False, unique=True),
                  col("status"), col("expires_at", DateTime), Column("approved_by", String),
                  Column("approved_at", DateTime), Column("rejection_reason", Text),
                  constraints=(CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','EXPIRED')"),))
actions = table("decision", "actions", Column("recommendation_id", String, ForeignKey("decision.recommendations.id"), nullable=False, unique=True),
                col("action_type"), col("status"), col("execution_time", DateTime), col("effective_at", DateTime),
                col("request_payload", JSON), col("response_payload", JSON),
                constraints=(CheckConstraint("status IN ('PENDING','RUNNING','SUCCESS','FAILED')"),))
expected_impacts = table("decision", "expected_impacts", Column("recommendation_id", String, ForeignKey("decision.recommendations.id"), nullable=False, unique=True),
                        col("metric"), col("expected_percent", Float), col("window_days", Integer))
actual_impacts = table("decision", "actual_impacts", Column("action_id", String, ForeignKey("decision.actions.id"), nullable=False, unique=True),
                      col("absolute_impact", Float), col("percentage_impact", Float), col("difference_from_expected", Float),
                      col("lower", Float), col("upper", Float), col("confidence", Float), col("method"),
                      col("pre_start", DateTime), col("post_end", DateTime), col("sample_size", Integer))
outcomes = table("decision", "outcomes", Column("action_id", String, ForeignKey("decision.actions.id"), nullable=False, unique=True),
                 col("outcome"), col("description", Text))
lessons = table("decision", "lessons", Column("incident_id", String, ForeignKey("decision.incidents.id"), nullable=False, unique=True),
                col("lesson", Text))
workflow_runs = table("audit", "workflow_runs", col("workflow_name"), col("run_id"), col("status"), col("details", JSON))
model_runs = table("audit", "model_runs", col("model_name"), col("run_id"), col("parameters", JSON), col("result", JSON))
api_requests = table("audit", "api_requests", col("request_id"), col("method"), col("path"),
                     col("status_code", Integer), col("duration_ms", Float))

for target in (web_sessions, orders, metric_observations, anomalies, forecasts):
    Index(f"ix_{target.name}_timestamp", target.c.timestamp)
Index("ix_incidents_similarity", incidents.c.metric, incidents.c.driver, incidents.c.dimension_value)
Index("ix_orders_cohort", orders.c.cohort_id)
Index("ix_refunds_order", refunds.c.order_id)
Index("ix_orders_customer", orders.c.customer_id)

RAW_TABLES = [customers, products, web_sessions, orders, payments, refunds, marketing_campaigns,
              support_tickets, subscriptions, application_events, deployments, operational_incidents]
