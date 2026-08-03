"""Verify Phase 0 runtime, configuration, logging, ODBC, and permissions."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import logging
import platform
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from decision_intelligence.logging_config import configure_logging  # noqa: E402
from decision_intelligence.settings import ConfigurationError, load_settings  # noqa: E402


@dataclass(frozen=True)
class CheckResult:
    """A named verification outcome."""

    name: str
    status: str
    detail: str


def _check_python() -> CheckResult:
    version = sys.version_info
    passed = version.major == 3 and version.minor == 12
    return CheckResult("Python 3.12", "PASS" if passed else "FAIL", platform.python_version())


def _check_imports() -> CheckResult:
    modules = ("yaml", "dotenv")
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    return CheckResult(
        "Foundation dependencies",
        "FAIL" if missing else "PASS",
        f"missing: {', '.join(missing)}" if missing else "PyYAML and python-dotenv available",
    )


def _check_configuration() -> CheckResult:
    settings, database = load_settings(PROJECT_ROOT)
    detail = (
        f"environment={settings.environment}, database={database.database}, "
        f"seed={settings.random_seed}"
    )
    return CheckResult("Configuration", "PASS", detail)


def _check_logging() -> CheckResult:
    settings, _ = load_settings(PROJECT_ROOT)
    configure_logging(settings.config_dir / "logging.yaml", settings.log_level)
    logging.getLogger(__name__).info("Logging verification message")
    return CheckResult("Logging", "PASS", f"root level={settings.log_level}")


def _check_permissions() -> CheckResult:
    targets = (PROJECT_ROOT / "data" / "interim", PROJECT_ROOT / "models" / "artifacts")
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target, prefix="phase0_", delete=True):
            pass
    return CheckResult("Folder permissions", "PASS", f"writable targets={len(targets)}")


def _check_odbc() -> CheckResult:
    if importlib.util.find_spec("pyodbc") is None:
        return CheckResult("SQL Server ODBC", "WARN", "pyodbc not installed; required in Phase 1")
    pyodbc = importlib.import_module("pyodbc")
    drivers = pyodbc.drivers()
    matches = [driver for driver in drivers if "ODBC Driver 18 for SQL Server" in driver]
    return CheckResult(
        "SQL Server ODBC",
        "PASS" if matches else "WARN",
        matches[0] if matches else "ODBC Driver 18 for SQL Server not found; required in Phase 1",
    )


def _check_future_imports() -> CheckResult:
    modules = (
        "pandas",
        "sqlalchemy",
        "sklearn",
        "xgboost",
        "lightgbm",
        "mlforecast",
        "shap",
        "ortools",
        "fastapi",
        "mlflow",
    )
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    return CheckResult(
        "Future stack dependencies",
        "WARN" if missing else "PASS",
        f"not installed yet: {', '.join(missing)}"
        if missing
        else "all future stack imports available",
    )


def run_checks(strict_future_stack: bool = False) -> tuple[list[CheckResult], int]:
    """Run independent checks; return outcomes and a stable process exit code."""
    checks: Sequence[Callable[[], CheckResult]] = (
        _check_python,
        _check_imports,
        _check_configuration,
        _check_logging,
        _check_permissions,
        _check_odbc,
        _check_future_imports,
    )
    results: list[CheckResult] = []
    for check in checks:
        try:
            results.append(check())
        except (ConfigurationError, OSError, ImportError, ValueError) as exc:
            results.append(CheckResult(check.__name__, "FAIL", str(exc)))
    if strict_future_stack:
        results = [
            CheckResult(result.name, "FAIL", result.detail)
            if result.status == "WARN"
            and result.name in {"SQL Server ODBC", "Future stack dependencies"}
            else result
            for result in results
        ]
    return results, 1 if any(result.status == "FAIL" for result in results) else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Print a readable verification report and return zero only on success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-future-stack", action="store_true")
    args = parser.parse_args(argv)
    results, exit_code = run_checks(args.strict_future_stack)
    print("AI Decision Intelligence Platform - Environment Verification")
    for result in results:
        print(f"[{result.status}] {result.name}: {result.detail}")
    message = (
        "ENVIRONMENT VERIFICATION PASSED" if exit_code == 0 else "ENVIRONMENT VERIFICATION FAILED"
    )
    print(message)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
