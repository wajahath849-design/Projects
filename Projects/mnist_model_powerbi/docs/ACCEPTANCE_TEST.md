# Acceptance test

Power BI work starts only after all checks pass:

1. `REGISTER_MODELS.bat` enables all nine models.
2. `VERIFY_PROJECT.bat` reports success.
3. `START_PROJECT.bat` starts API and watcher.
4. `http://127.0.0.1:8000/health` returns `status: ok`.
5. Copy a unique digit image into `data/incoming`.
6. SQL contains one `ImageBatch` row, nine `ModelPrediction` rows and 90 `ClassProbability` rows.
7. A single model failure produces `PartialSuccess`, not a total batch failure.
8. `vw_LatestCompletedImage` returns one retained image.
9. `vw_ModelAgreement` returns consensus and agreement rate.
10. A duplicate file is deleted from incoming and stored as a `Duplicate` batch.
