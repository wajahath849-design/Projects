from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

import numpy as np

from . import config
from .db import connect, write_event
from .image_ops import (
    actual_class_from_filename,
    image_quality,
    save_display_png,
    save_processed_preview_png,
    sha256_file,
)
from .model_registry import ModelLoadResult
from .probability import normalise_probabilities


class Processor:
    def __init__(self, models: ModelLoadResult):
        self.loaded = models.loaded
        self.unavailable = models.unavailable

    @staticmethod
    def _wait_for_stable_file(path: Path) -> None:
        deadline = time.monotonic() + config.STABLE_FILE_TIMEOUT_SECONDS
        previous: tuple[int, int] | None = None
        stable_checks = 0
        while time.monotonic() < deadline:
            try:
                stat = path.stat()
                state = (stat.st_size, stat.st_mtime_ns)
            except FileNotFoundError:
                time.sleep(0.25)
                continue
            if stat.st_size > 0 and state == previous:
                stable_checks += 1
                if stable_checks >= 3:
                    return
            else:
                stable_checks = 0
                previous = state
            time.sleep(0.25)
        raise TimeoutError(f"File did not become stable: {path.name}")

    @staticmethod
    def _record_failed_prediction(batch_id, cfg: dict, error: str) -> None:
        with connect() as conn:
            conn.cursor().execute(
                """INSERT dbo.ModelPrediction(BatchID,ModelID,PredictionStatus,ErrorMessage)
                   VALUES(?,?,N'Failed',?)""",
                batch_id, cfg["model_id"], str(error)[:4000],
            )
            conn.commit()

    @staticmethod
    def _apply_retention(current_batch_id) -> None:
        with connect() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                """SELECT BatchID,StoredFileName,ProcessedFileName,
                          CASE
                              WHEN COALESCE(CompletedAt,DetectedAt)
                                   <= DATEADD(SECOND,-?,SYSUTCDATETIME())
                              THEN 1 ELSE 0
                          END AS RetentionEligible
                   FROM dbo.ImageBatch
                   WHERE StoredFileName IS NOT NULL AND ProcessingStatus IN(N'Completed',N'PartialSuccess')
                   ORDER BY COALESCE(CompletedAt,DetectedAt) DESC, BatchID DESC""",
                config.IMAGE_RETENTION_GRACE_SECONDS,
            ).fetchall()
            current_id = str(current_batch_id).strip("{}").lower()
            for row in rows[config.MAX_RETAINED_IMAGES:]:
                row_id = str(row.BatchID).strip("{}").lower()
                if row_id == current_id or not bool(row.RetentionEligible):
                    continue
                filename = Path(str(row.StoredFileName)).name
                (config.PROCESSED / filename).unlink(missing_ok=True)
                if row.ProcessedFileName:
                    processed_filename = Path(str(row.ProcessedFileName)).name
                    (config.PROCESSED / processed_filename).unlink(missing_ok=True)
                cursor.execute(
                    """UPDATE dbo.ImageBatch SET StoredFileName=NULL,ImageRelativePath=NULL,ImageUrl=NULL,
                       ProcessedFileName=NULL,ProcessedImageRelativePath=NULL,ProcessedImageUrl=NULL
                       WHERE BatchID=?""", row.BatchID,
                )
            conn.commit()

    def process(self, source) -> str:
        started = time.perf_counter()
        source = Path(source)
        self._wait_for_stable_file(source)
        batch_id = str(uuid.uuid4())
        image_hash = sha256_file(source)
        original_name = source.name

        with connect() as conn:
            duplicate = conn.cursor().execute(
                """SELECT TOP(1) BatchID FROM dbo.ImageBatch
                   WHERE ImageHash=? AND IsDuplicate=0 AND ProcessingStatus IN(N'Completed',N'PartialSuccess')
                   ORDER BY DetectedAt DESC""", image_hash,
            ).fetchone()
        if duplicate:
            with connect() as conn:
                conn.cursor().execute(
                    """INSERT dbo.ImageBatch(BatchID,ImageHash,OriginalFileName,CompletedAt,ProcessingStatus,
                       IsDuplicate,DuplicateOfBatchID,PipelineVersion,MetricsEligible)
                       VALUES(?,?,?,SYSUTCDATETIME(),N'Duplicate',1,?,?,1)""",
                    batch_id, image_hash, original_name, duplicate[0], config.PIPELINE_VERSION,
                )
                conn.commit()
            source.unlink(missing_ok=True)
            write_event("Information", "Processor", "DUPLICATE_IMAGE", f"Duplicate skipped: {original_name}", batch_id)
            return batch_id

        stored_name = f"{batch_id}.png"
        stored_path = config.PROCESSED / stored_name
        processed_name = f"{batch_id}_processed_28x28.png"
        processed_path = config.PROCESSED / processed_name
        actual_class = actual_class_from_filename(original_name)

        try:
            width, height, brightness, contrast, blur_score = image_quality(source)
            save_display_png(source, stored_path)
            save_processed_preview_png(source, processed_path)
            image_url = f"{config.PUBLIC_API_BASE_URL}/images/{stored_name}"
            processed_image_url = f"{config.PUBLIC_API_BASE_URL}/images/{processed_name}"
            with connect() as conn:
                conn.cursor().execute(
                    """INSERT dbo.ImageBatch(BatchID,ImageHash,OriginalFileName,StoredFileName,ImageRelativePath,
                       ImageUrl,ProcessedFileName,ProcessedImageRelativePath,ProcessedImageUrl,ActualClass,
                       OriginalWidth,OriginalHeight,Brightness,Contrast,BlurScore,ProcessingStatus,
                       PipelineVersion,MetricsEligible)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,N'Processing',?,1)""",
                    batch_id, image_hash, original_name, stored_name, f"data/processed/{stored_name}", image_url,
                    processed_name, f"data/processed/{processed_name}", processed_image_url,
                    actual_class, width, height, brightness, contrast, blur_score, config.PIPELINE_VERSION,
                )
                conn.commit()

            succeeded = 0
            failed = 0

            for cfg, reason in self.unavailable:
                self._record_failed_prediction(batch_id, cfg, f"Model unavailable at startup: {reason}")
                failed += 1

            for _, (adapter, cfg) in self.loaded.items():
                try:
                    result = adapter.predict(str(source))
                    probabilities = normalise_probabilities(result["probabilities"], len(adapter.class_map))
                    top = np.argsort(probabilities)[::-1][:3]
                    labels = [adapter.class_map[str(int(index))] for index in top]
                    confidence = float(probabilities[top[0]])
                    second_confidence = float(probabilities[top[1]])
                    with connect() as conn:
                        cursor = conn.cursor()
                        prediction_id = cursor.execute(
                            """INSERT dbo.ModelPrediction(BatchID,ModelID,PredictedClass,Confidence,SecondClass,
                               SecondConfidence,ThirdClass,ThirdConfidence,ConfidenceMargin,IsCorrect,IsUncertain,
                               InferenceMilliseconds,PredictionStatus)
                               OUTPUT INSERTED.PredictionID VALUES(?,?,?,?,?,?,?,?,?,?,?,?,N'Succeeded')""",
                            batch_id, cfg["model_id"], labels[0], confidence, labels[1], second_confidence,
                            labels[2], float(probabilities[top[2]]), confidence - second_confidence,
                            None if actual_class is None else int(labels[0] == actual_class),
                            int(confidence < config.CONFIDENCE_THRESHOLD), float(result["inference_ms"]),
                        ).fetchone()[0]
                        cursor.fast_executemany = True
                        cursor.executemany(
                            "INSERT dbo.ClassProbability(PredictionID,ClassLabel,Probability) VALUES(?,?,?)",
                            [(prediction_id, adapter.class_map[str(i)], float(value)) for i, value in enumerate(probabilities)],
                        )
                        conn.commit()
                    succeeded += 1
                except Exception as exc:
                    failed += 1
                    self._record_failed_prediction(batch_id, cfg, str(exc))
                    write_event("Error", "Model", "MODEL_PREDICTION_FAILED", f"{cfg['display_name']}: {exc}", batch_id, cfg["model_id"])

            status = "Completed" if succeeded > 0 and failed == 0 else "PartialSuccess" if succeeded > 0 else "Failed"
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            with connect() as conn:
                conn.cursor().execute(
                    """UPDATE dbo.ImageBatch SET CompletedAt=SYSUTCDATETIME(),ProcessingStatus=?,
                       ProcessingMilliseconds=?,ErrorMessage=? WHERE BatchID=?""",
                    status, elapsed_ms, None if succeeded else "No enabled model completed successfully", batch_id,
                )
                if succeeded == 0:
                    conn.cursor().execute(
                        """UPDATE dbo.ImageBatch SET StoredFileName=NULL,ImageRelativePath=NULL,ImageUrl=NULL,
                           ProcessedFileName=NULL,ProcessedImageRelativePath=NULL,ProcessedImageUrl=NULL
                           WHERE BatchID=?""",
                        batch_id,
                    )
                conn.commit()

            if succeeded:
                source.unlink(missing_ok=True)
                self._apply_retention(batch_id)
            else:
                stored_path.unlink(missing_ok=True)
                processed_path.unlink(missing_ok=True)
                shutil.move(str(source), str(config.FAILED / f"{batch_id}_{original_name}"))

            write_event(
                "Information" if succeeded else "Error", "Processor", "BATCH_COMPLETED",
                f"{original_name}: {status}; {succeeded} succeeded; {failed} failed", batch_id,
            )
            return batch_id
        except Exception as exc:
            stored_path.unlink(missing_ok=True)
            processed_path.unlink(missing_ok=True)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            try:
                with connect(retries=2) as conn:
                    exists = conn.cursor().execute("SELECT 1 FROM dbo.ImageBatch WHERE BatchID=?", batch_id).fetchone()
                    if exists:
                        conn.cursor().execute(
                            """UPDATE dbo.ImageBatch SET CompletedAt=SYSUTCDATETIME(),ProcessingStatus=N'Failed',
                               ProcessingMilliseconds=?,ErrorMessage=?,StoredFileName=NULL,ImageRelativePath=NULL,
                               ImageUrl=NULL,ProcessedFileName=NULL,ProcessedImageRelativePath=NULL,ProcessedImageUrl=NULL
                               WHERE BatchID=?""", elapsed_ms, str(exc)[:4000], batch_id,
                        )
                    else:
                        conn.cursor().execute(
                            """INSERT dbo.ImageBatch(BatchID,ImageHash,OriginalFileName,CompletedAt,ProcessingStatus,
                               ProcessingMilliseconds,ErrorMessage,PipelineVersion,MetricsEligible)
                               VALUES(?,?,?,SYSUTCDATETIME(),N'Failed',?,?,?,1)""",
                            batch_id, image_hash, original_name, elapsed_ms, str(exc)[:4000], config.PIPELINE_VERSION,
                        )
                    conn.commit()
            except Exception:
                pass
            if source.exists():
                shutil.move(str(source), str(config.FAILED / f"{batch_id}_{original_name}"))
            write_event("Error", "Processor", "BATCH_FAILED", f"{original_name}: {exc}", batch_id)
            raise
