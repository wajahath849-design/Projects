"""Command-line entry point for implemented platform phases."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from decision_intelligence.logging_config import configure_logging
from decision_intelligence.settings import ConfigurationError, load_settings


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser using only commands available in the current phase."""
    parser = argparse.ArgumentParser(prog="decision-intelligence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-environment", help="Verify Phase 0 prerequisites")
    verify.add_argument("--strict-future-stack", action="store_true")
    initialize = subparsers.add_parser(
        "initialize-database", help="Create and verify the Phase 1 SQL Server database"
    )
    initialize.add_argument("--verify-only", action="store_true")
    load_data = subparsers.add_parser("load-data", help="Validate and load M5 CSV files")
    load_data.add_argument("--sample", action="store_true")
    load_data.add_argument("--data-directory", type=Path)
    load_data.add_argument("--chunk-size", type=int)
    generate_data = subparsers.add_parser(
        "generate-data", help="Generate and load synthetic enterprise operations"
    )
    generate_data.add_argument("--sample", action="store_true")
    generate_data.add_argument("--no-load", action="store_true")
    run_quality = subparsers.add_parser("run-quality", help="Run and persist data-quality checks")
    run_quality.add_argument("--output-directory", type=Path)
    build_features = subparsers.add_parser(
        "build-features", help="Build leakage-safe forecasting features"
    )
    build_features.add_argument("--full", action="store_true")
    build_features.add_argument("--output", type=Path)
    subparsers.add_parser("train-models", help="Train, compare, and select forecasting models")
    subparsers.add_parser("evaluate-models", help="Show persisted model evaluation")
    subparsers.add_parser("generate-forecasts", help="Generate and persist 7/30/90-day forecasts")
    subparsers.add_parser("generate-explanations", help="Generate and persist SHAP explanations")
    subparsers.add_parser("inventory", help="Calculate and persist inventory intelligence")
    subparsers.add_parser("optimize", help="Run constraint-validated replenishment optimization")
    subparsers.add_parser("run-scenarios", help="Run all configured scenario simulations")
    subparsers.add_parser("export-powerbi", help="Apply and export the Power BI package")
    subparsers.add_parser("verify-project", help="Run the complete project verification")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Execute a CLI command and return a meaningful process exit code."""
    args = build_parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    try:
        settings, _ = load_settings(root)
        configure_logging(settings.config_dir / "logging.yaml", settings.log_level)
        if args.command == "verify-environment":
            command = [sys.executable, str(root / "scripts" / "verify_environment.py")]
            if args.strict_future_stack:
                command.append("--strict-future-stack")
            return subprocess.run(command, check=False).returncode
        if args.command == "initialize-database":
            command = [sys.executable, str(root / "scripts" / "initialize_database.py")]
            if args.verify_only:
                command.append("--verify-only")
            return subprocess.run(command, check=False).returncode
        if args.command == "load-data":
            command = [sys.executable, str(root / "scripts" / "load_m5_data.py")]
            if args.sample:
                command.append("--sample")
            if args.data_directory:
                command.extend(["--data-directory", str(args.data_directory)])
            if args.chunk_size:
                command.extend(["--chunk-size", str(args.chunk_size)])
            return subprocess.run(command, check=False).returncode
        if args.command == "generate-data":
            command = [sys.executable, str(root / "scripts" / "generate_enterprise_data.py")]
            if args.sample:
                command.append("--sample")
            if args.no_load:
                command.append("--no-load")
            return subprocess.run(command, check=False).returncode
        if args.command == "run-quality":
            command = [sys.executable, str(root / "scripts" / "run_data_quality.py")]
            if args.output_directory:
                command.extend(["--output-directory", str(args.output_directory)])
            return subprocess.run(command, check=False).returncode
        if args.command == "build-features":
            command = [sys.executable, str(root / "scripts" / "build_features.py")]
            if args.full:
                command.append("--full")
            if args.output:
                command.extend(["--output", str(args.output)])
            return subprocess.run(command, check=False).returncode
        script_commands = {
            "train-models": "train_models.py",
            "evaluate-models": "evaluate_models.py",
            "generate-forecasts": "generate_forecasts.py",
            "generate-explanations": "generate_explanations.py",
            "inventory": "calculate_inventory_intelligence.py",
            "optimize": "run_optimization.py",
            "run-scenarios": "run_scenarios.py",
            "export-powerbi": "export_power_bi_data.py",
            "verify-project": "verify_project.py",
        }
        if args.command in script_commands:
            return subprocess.run(
                [sys.executable, str(root / "scripts" / script_commands[args.command])],
                check=False,
            ).returncode
    except ConfigurationError as exc:
        logging.basicConfig(level=logging.ERROR)
        logging.getLogger(__name__).error("Configuration failed: %s", exc)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
