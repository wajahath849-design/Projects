"""Tests for the environment verification report."""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "verify_environment.py"
SPEC = importlib.util.spec_from_file_location("verify_environment", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_foundation_checks_have_unique_names() -> None:
    results, _ = MODULE.run_checks()
    names = [result.name for result in results]
    assert len(names) == len(set(names))
    assert {"Python 3.12", "Configuration", "Logging", "Folder permissions"}.issubset(names)


def test_strict_mode_promotes_future_warnings() -> None:
    normal = MODULE.CheckResult("Future stack dependencies", "WARN", "missing")
    assert normal.status == "WARN"
    results, exit_code = MODULE.run_checks(strict_future_stack=True)
    future = next(result for result in results if result.name == "Future stack dependencies")
    if future.detail.startswith("not installed yet"):
        assert future.status == "FAIL"
        assert exit_code == 1
