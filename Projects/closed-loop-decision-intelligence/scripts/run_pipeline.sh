#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python -m src.cli run-pipeline "$@"
