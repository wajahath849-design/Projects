from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import config
from .db import connect

app = FastAPI(title="AI Model Analytics API", version="4.0.0")


class FeedbackRequest(BaseModel):
    batch_id: str
    corrected_class: str = Field(pattern=r"^[0-9]$")
    reviewer: str | None = Field(default=None, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)


def _row_dict(cursor, row):
    return {column[0]: value for column, value in zip(cursor.description, row)}


@app.get("/health")
def health():
    try:
        with connect(retries=2) as conn:
            cursor = conn.cursor()
            row = cursor.execute(
                """SELECT DB_NAME() AS DatabaseName,
                   (SELECT COUNT(*) FROM dbo.ModelRegistry WHERE IsEnabled=1) AS EnabledModels,
                   (SELECT COUNT(*) FROM dbo.ModelRegistry WHERE IsEnabled=1 AND IsVerified=1) AS VerifiedModels"""
            ).fetchone()
        return {
            "status": "ok", "database": row[0], "enabled_models": row[1],
            "verified_models": row[2], "utc_time": datetime.now(timezone.utc),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/models")
def models():
    with connect() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """SELECT ModelKey,ModelName,Framework,Architecture,IsEnabled,IsTrained,IsVerified,
               ValidationAccuracy,TestAccuracy FROM dbo.ModelRegistry ORDER BY ModelID"""
        ).fetchall()
        return [_row_dict(cursor, row) for row in rows]


@app.get("/images/{filename}")
def image(filename: str):
    safe_name = Path(filename).name
    path = config.PROCESSED / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found or removed by the retention policy")
    return FileResponse(path, media_type="image/png")


@app.get("/latest")
def latest():
    with connect() as conn:
        cursor = conn.cursor()
        row = cursor.execute("SELECT TOP(1) * FROM dbo.vw_LatestBatchSummary").fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="No completed prediction is available")
        return _row_dict(cursor, row)


@app.get("/latest-image")
def latest_image():
    with connect() as conn:
        row = conn.cursor().execute("SELECT TOP(1) StoredFileName FROM dbo.vw_LatestCompletedImage").fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="No retained completed image is available")
    return image(str(row[0]))


@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest):
    with connect() as conn:
        cursor = conn.cursor()
        exists = cursor.execute("SELECT 1 FROM dbo.ImageBatch WHERE BatchID=?", payload.batch_id).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Batch not found")
        cursor.execute(
            "INSERT dbo.HumanReview(BatchID,CorrectedClass,Reviewer,Notes) VALUES(?,?,?,?)",
            payload.batch_id, payload.corrected_class, payload.reviewer, payload.notes,
        )
        cursor.execute("UPDATE dbo.ImageBatch SET ActualClass=? WHERE BatchID=?", payload.corrected_class, payload.batch_id)
        cursor.execute(
            """UPDATE dbo.ModelPrediction SET IsCorrect=CASE WHEN PredictedClass=? THEN 1 ELSE 0 END
               WHERE BatchID=? AND PredictionStatus=N'Succeeded'""",
            payload.corrected_class, payload.batch_id,
        )
        conn.commit()
    return {"status": "saved", "batch_id": payload.batch_id}
