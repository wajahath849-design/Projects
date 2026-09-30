#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python -m src.cli generate-data --months 24 --seed 42 "$@"
