#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
# Container execution uses the same installed environment as n8n's analytical API.
docker compose exec api python -m src.cli demo "$@"
