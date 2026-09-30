#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python scripts/configure.py
docker compose up -d --build
