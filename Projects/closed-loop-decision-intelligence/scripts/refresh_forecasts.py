"""Rebuild existing derived forecasts after quality-screening logic changes.

Existing source data, approval history and actions remain unchanged. Model audits
record the quality-screened method version and number of imputed observations.
"""
from api.services.decisions import forecast_incident
from src.common import models as m
from src.common.config import offline_url
from src.common.db import make_engine
from src.common.store import records
from src.metrics.engine import load_mart

engine = make_engine(offline_url())
with engine.connect() as connection:
    identifiers = {row["incident_id"] for row in records(connection, m.forecasts)}
frame = load_mart(engine)
for incident_id in sorted(identifiers):
    print(incident_id, forecast_incident(engine, incident_id, frame, force=True), flush=True)
