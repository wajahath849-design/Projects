"""Run the bounded local telemetry simulator from the command line."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.realtime.configuration import RealtimeConfig
from src.realtime.simulator import BufferedTelemetryStream, TelemetrySimulator
from src.realtime.store import RealtimeStore
from src.realtime.streaming_analytics import StreamingAnalyticsService


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate isolated synthetic telemetry")
    parser.add_argument(
        "--ticks", type=int, default=12,
        help="Number of ticks to run; use 0 to continue until interrupted",
    )
    parser.add_argument("--speed", type=float, default=None)
    parser.add_argument("--session", type=str, default=None)
    args = parser.parse_args()
    if args.ticks < 0:
        parser.error("--ticks must be zero or a positive integer")

    config = RealtimeConfig.from_yaml(settings.realtime_config_path)
    store = RealtimeStore(
        settings.realtime_database_path,
        settings.database_path,
        PROJECT_ROOT / "database/realtime_schema.sql",
    )
    store.initialize()
    speed = (
        args.speed if args.speed is not None else config.default_speed_multiplier
    )
    session_id = store.create_session(
        simulation_session_id=args.session,
        speed_multiplier=speed,
        random_seed=config.random_seed,
        retention_hours=config.retention_hours,
        max_events=config.max_events_per_session,
    )
    simulator = TelemetrySimulator(
        settings.database_path,
        random_seed=config.random_seed,
        tick_interval_seconds=config.tick_interval_seconds,
        server_sample_size_per_facility=config.server_sample_size_per_facility,
    )
    stream = BufferedTelemetryStream(config.queue_max_batches)
    analytics = StreamingAnalyticsService(
        store,
        config,
        PROJECT_ROOT / "analytics/live_health_weights.yaml",
    )
    current = datetime.now(timezone.utc)
    processed_events = 0
    processed_batches = 0
    try:
        while args.ticks == 0 or processed_batches < args.ticks:
            stream.publish(simulator.generate_tick(session_id, current))
            outcomes = stream.drain_with(analytics.process)
            processed_events += sum(
                outcome.ingestion.total_inserted for outcome in outcomes
            )
            processed_batches += len(outcomes)
            current += timedelta(seconds=config.tick_interval_seconds)
            if args.ticks == 0 or processed_batches < args.ticks:
                time.sleep(config.tick_interval_seconds / speed)
        store.set_session_status(session_id, "completed")
    except KeyboardInterrupt:
        store.set_session_status(session_id, "stopped")
    print(
        f"Session {session_id}: {processed_events} events processed "
        f"across {processed_batches} batches."
    )


if __name__ == "__main__":
    main()
