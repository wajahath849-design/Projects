from __future__ import annotations

import os
import sys

import requests


api_url = os.getenv("INVENTORY_API_URL", "http://localhost:8000").rstrip("/")
api_key = os.getenv("INVENTORY_API_KEY") or os.getenv("API_KEY")

health = requests.get(f"{api_url}/health", timeout=10)
health.raise_for_status()
print("Health:", health.json())

if not api_key:
    print("API key not set; authenticated smoke test skipped.")
    raise SystemExit(0)

response = requests.post(
    f"{api_url}/jobs",
    headers={"X-API-Key": api_key},
    json={"job_type": "FULL_PIPELINE", "payload": {}, "requested_by": "smoke-test", "priority": 100},
    timeout=10,
)
if not response.ok:
    print(response.text, file=sys.stderr)
response.raise_for_status()
print("Queued job:", response.json())
