"""Reapply incident promotion policies to stored observations, then investigate.

Useful after a rule change; does not regenerate source data or approve any action.
"""
import argparse

from api.services.orchestration import stage
from src.common.config import offline_url
from src.common.db import make_engine
from src.common.logging import configure_logging

parser = argparse.ArgumentParser()
parser.add_argument("--offline", action="store_true")
args = parser.parse_args()
configure_logging()
engine = make_engine(offline_url() if args.offline else None)
for name in ["anomalies", "investigation", "forecast", "decisions"]:
    print(stage(engine, name), flush=True)
