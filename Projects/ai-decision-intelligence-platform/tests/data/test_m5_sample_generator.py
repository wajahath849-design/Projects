"""Tests for deterministic synthetic M5 sample generation."""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate_m5_sample.py"
SPEC = importlib.util.spec_from_file_location("generate_m5_sample", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_sample_generation_is_reproducible(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    counts_a = MODULE.generate_sample(first, seed=42, days=14)
    counts_b = MODULE.generate_sample(second, seed=42, days=14)
    assert counts_a == counts_b
    for name in ("calendar.csv", "sales_train_validation.csv", "sell_prices.csv"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
