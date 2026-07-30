from __future__ import annotations

import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.jobs import enqueue_job
from app.schemas import JobRequest, JobResponse, OverrideApprovalRequest, OverrideRequest


settings = get_settings()
app = FastAPI(
    title="Inventory Replenishment API",
    version="1.0.0",
    description="Validated bridge between Excel/VBA operations and the Python/PostgreSQL replenishment engine.",
)
DbSession = Annotated[Session, Depends(get_session)]


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@app.get("/health")
def health(session: DbSession) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/jobs", response_model=JobResponse, dependencies=[Depends(require_api_key)])
def create_job(request: JobRequest, session: DbSession) -> JobResponse:
    job_id = enqueue_job(
        session,
        request.job_type,
        request.payload,
        request.requested_by,
        request.priority,
    )
    return JobResponse(job_id=job_id, status="QUEUED")


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job(job_id: UUID, session: DbSession) -> dict:
    row = session.execute(
        text(
            """
            SELECT job_id, job_type, status, priority, attempts, max_attempts, requested_by, created_at,
                   started_at, finished_at, error_message, result
            FROM inventory.pipeline_jobs
            WHERE job_id = :job_id
            """
        ),
        {"job_id": job_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@app.post("/overrides", status_code=201, dependencies=[Depends(require_api_key)])
def submit_override(request: OverrideRequest, session: DbSession) -> dict:
    identifiers = session.execute(
        text(
            """
            SELECT w.warehouse_id, s.sku_id
            FROM inventory.dim_warehouse w
            CROSS JOIN inventory.dim_sku s
            WHERE w.warehouse_code = :warehouse_code
              AND s.sku_code = :sku_code
              AND w.active = TRUE
              AND s.active = TRUE
            """
        ),
        {"warehouse_code": request.warehouse_code, "sku_code": request.sku_code},
    ).mappings().first()
    if identifiers is None:
        raise HTTPException(status_code=400, detail="Unknown or inactive warehouse/SKU")

    row = session.execute(
        text(
            """
            INSERT INTO inventory.operational_overrides
                (warehouse_id, sku_id, override_type, numeric_value, text_value,
                 effective_from, effective_to, reason, submitted_by, status, source)
            VALUES
                (:warehouse_id, :sku_id, :override_type, :numeric_value, :text_value,
                 :effective_from, :effective_to, :reason, :submitted_by, 'PENDING', 'EXCEL')
            RETURNING override_id, status, created_at
            """
        ),
        {
            **dict(identifiers),
            **request.model_dump(),
        },
    ).mappings().one()
    session.commit()
    return {
        **dict(row),
        "message": "Override recorded and awaiting approval. No replenishment values change until approval.",
    }


@app.post("/overrides/{override_id}/decision", dependencies=[Depends(require_api_key)])
def decide_override(override_id: int, request: OverrideApprovalRequest, session: DbSession) -> dict:
    new_status = "APPROVED" if request.approve else "REJECTED"
    row = session.execute(
        text(
            """
            UPDATE inventory.operational_overrides
            SET status = :status,
                approved_by = :approved_by,
                decision_at = CURRENT_TIMESTAMP
            WHERE override_id = :override_id
              AND status = 'PENDING'
            RETURNING override_id, status, warehouse_id, sku_id
            """
        ),
        {"status": new_status, "approved_by": request.approved_by, "override_id": override_id},
    ).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pending override not found")
    session.commit()

    job_id = None
    if request.approve:
        job_id = enqueue_job(
            session,
            "OVERRIDE_RECALC",
            {"override_id": override_id, "warehouse_id": row["warehouse_id"], "sku_id": row["sku_id"]},
            request.approved_by,
            priority=20,
        )
    return {**dict(row), "job_id": job_id}
