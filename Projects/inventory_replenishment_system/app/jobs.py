from __future__ import annotations

import json
import logging
from threading import Event, Thread
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.ingestion import ingest_dataset
from app.document_ingestion import ingest_supplier_document
from app.external_signals import ingest_external_signal
from app.pipeline import run_full_pipeline, run_replenishment
from app.network_rebalancing import run_network_rebalancing


logger = logging.getLogger(__name__)
settings = get_settings()


def _validated_ingestion_path(file_path: str) -> str:
    candidate = Path(file_path).expanduser().resolve()
    roots = [Path(root).expanduser().resolve() for root in settings.ingestion_roots]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise ValueError(f"File path is outside allowed ingestion roots: {candidate}")
    return str(candidate)


def enqueue_job(
    session: Session,
    job_type: str,
    payload: dict[str, Any],
    requested_by: str,
    priority: int = 100,
) -> UUID:
    job_id = uuid4()
    session.execute(
        text(
            """
            INSERT INTO inventory.pipeline_jobs
                (job_id, job_type, payload, requested_by, priority)
            VALUES
                (:job_id, :job_type, CAST(:payload AS JSONB), :requested_by, :priority)
            """
        ),
        {
            "job_id": job_id,
            "job_type": job_type,
            "payload": json.dumps(payload),
            "requested_by": requested_by,
            "priority": priority,
        },
    )
    session.commit()
    return job_id


def claim_next_job(session: Session) -> dict[str, Any] | None:
    row = session.execute(
        text(
            """
            WITH next_job AS (
                SELECT job_id
                FROM inventory.pipeline_jobs
                WHERE status = 'QUEUED'
                ORDER BY priority ASC, created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE inventory.pipeline_jobs j
            SET status = 'RUNNING',
                started_at = CURRENT_TIMESTAMP,
                heartbeat_at = CURRENT_TIMESTAMP,
                attempts = attempts + 1
            FROM next_job
            WHERE j.job_id = next_job.job_id
            RETURNING j.job_id, j.job_type, j.payload, j.requested_by, j.attempts, j.max_attempts
            """
        )
    ).mappings().first()
    session.commit()
    return dict(row) if row else None


def requeue_stale_jobs(session: Session) -> tuple[int, int]:
    """Recover jobs abandoned by a terminated worker and cap retry loops."""
    failed = session.execute(
        text(
            """
            UPDATE inventory.pipeline_jobs
            SET status = 'FAILED',
                finished_at = CURRENT_TIMESTAMP,
                error_message = CONCAT_WS(E'\n', NULLIF(error_message, ''), 'Maximum attempts reached after stale worker heartbeat')
            WHERE status = 'RUNNING'
              AND COALESCE(heartbeat_at, started_at, created_at)
                    < CURRENT_TIMESTAMP - make_interval(mins => :stale_minutes)
              AND attempts >= max_attempts
            """
        ),
        {"stale_minutes": settings.job_stale_minutes},
    ).rowcount or 0
    requeued = session.execute(
        text(
            """
            UPDATE inventory.pipeline_jobs
            SET status = 'QUEUED',
                started_at = NULL,
                heartbeat_at = NULL,
                error_message = CONCAT_WS(E'\n', NULLIF(error_message, ''), 'Requeued after stale worker heartbeat')
            WHERE status = 'RUNNING'
              AND COALESCE(heartbeat_at, started_at, created_at)
                    < CURRENT_TIMESTAMP - make_interval(mins => :stale_minutes)
              AND attempts < max_attempts
            """
        ),
        {"stale_minutes": settings.job_stale_minutes},
    ).rowcount or 0
    session.commit()
    return int(requeued), int(failed)


def heartbeat_job(job_id: UUID) -> None:
    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE inventory.pipeline_jobs
                SET heartbeat_at = CURRENT_TIMESTAMP
                WHERE job_id = :job_id AND status = 'RUNNING'
                """
            ),
            {"job_id": job_id},
        )
        session.commit()


def _heartbeat_loop(job_id: UUID, stop_event: Event) -> None:
    while not stop_event.wait(settings.job_heartbeat_seconds):
        try:
            heartbeat_job(job_id)
        except Exception:
            logger.exception("Heartbeat update failed for job %s", job_id)


def complete_job(job_id: UUID, result: dict[str, Any]) -> None:
    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE inventory.pipeline_jobs
                SET status = 'SUCCEEDED',
                    finished_at = CURRENT_TIMESTAMP,
                    heartbeat_at = CURRENT_TIMESTAMP,
                    result = CAST(:result AS JSONB),
                    error_message = NULL
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id, "result": json.dumps(result, default=str)},
        )
        session.commit()


def fail_job(job_id: UUID, exc: Exception) -> None:
    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE inventory.pipeline_jobs
                SET status = 'FAILED',
                    finished_at = CURRENT_TIMESTAMP,
                    heartbeat_at = CURRENT_TIMESTAMP,
                    error_message = :error_message
                WHERE job_id = :job_id
                """
            ),
            {"job_id": job_id, "error_message": str(exc)[:4000]},
        )
        session.commit()


def execute_job(job: dict[str, Any]) -> dict[str, Any]:
    job_type = str(job["job_type"])
    payload = dict(job.get("payload") or {})
    if job_type in {"FULL_PIPELINE", "FORECAST"}:
        return run_full_pipeline(horizon_days=payload.get("horizon_days"))
    if job_type == "OVERRIDE_RECALC":
        with SessionLocal() as session:
            model_run_id = session.execute(
                text(
                    """
                    SELECT model_run_id
                    FROM inventory.model_runs
                    WHERE status = 'SUCCEEDED'
                    ORDER BY finished_at DESC NULLS LAST, model_run_id DESC
                    LIMIT 1
                    """
                )
            ).scalar_one_or_none()
            if model_run_id is None:
                return run_full_pipeline(horizon_days=payload.get("horizon_days"))
            recommendation_rows = run_replenishment(session, int(model_run_id))
            transfer_rows = run_network_rebalancing(session, int(model_run_id))
        return {
            "model_run_id": int(model_run_id),
            "recommendation_rows": recommendation_rows,
            "transfer_recommendation_rows": transfer_rows,
            "mode": "replenishment_only",
        }
    if job_type == "REPLENISHMENT":
        model_run_id = int(payload["model_run_id"])
        with SessionLocal() as session:
            rows = run_replenishment(session, model_run_id)
            transfer_rows = run_network_rebalancing(session, model_run_id)
        return {"model_run_id": model_run_id, "recommendation_rows": rows, "transfer_recommendation_rows": transfer_rows}
    if job_type == "INGEST_CSV":
        with SessionLocal() as session:
            result = ingest_dataset(session, payload["dataset_type"], _validated_ingestion_path(payload["file_path"]))
            session.commit()
        return result
    if job_type == "INGEST_DOCUMENT":
        with SessionLocal() as session:
            return ingest_supplier_document(
                session,
                _validated_ingestion_path(payload["file_path"]),
                supplier_code=payload.get("supplier_code"),
            )
    if job_type == "INGEST_EXTERNAL_SIGNAL":
        with SessionLocal() as session:
            return ingest_external_signal(
                session,
                url=payload["url"],
                allowed_hosts=settings.external_api_hosts,
                region=payload["region"],
                signal_type=payload["signal_type"],
                value_path=payload["value_path"],
                source_name=payload["source_name"],
                signal_date=date.fromisoformat(payload["signal_date"]) if payload.get("signal_date") else None,
                scale=float(payload.get("scale", 1.0)),
                offset=float(payload.get("offset", 0.0)),
                min_value=float(payload["min_value"]) if payload.get("min_value") is not None else None,
                max_value=float(payload["max_value"]) if payload.get("max_value") is not None else None,
            )
    raise ValueError(f"Unsupported job_type: {job_type}")


def process_one_job() -> bool:
    with SessionLocal() as session:
        requeued, failed = requeue_stale_jobs(session)
        if requeued or failed:
            logger.warning("Recovered stale jobs: requeued=%s failed=%s", requeued, failed)
        job = claim_next_job(session)
    if job is None:
        return False

    job_id = UUID(str(job["job_id"]))
    stop_event = Event()
    heartbeat_thread = Thread(
        target=_heartbeat_loop,
        args=(job_id, stop_event),
        name=f"job-heartbeat-{job_id}",
        daemon=True,
    )
    heartbeat_thread.start()
    try:
        result = execute_job(job)
        complete_job(job_id, result)
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        fail_job(job_id, exc)
    finally:
        stop_event.set()
        heartbeat_thread.join(timeout=2)
    return True
