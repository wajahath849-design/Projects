USE AIModelAnalytics;
GO

IF COL_LENGTH(N'dbo.ImageBatch', N'PipelineVersion') IS NULL
BEGIN
    ALTER TABLE dbo.ImageBatch
        ADD PipelineVersion nvarchar(30) NOT NULL
            CONSTRAINT DF_ImageBatch_PipelineVersion DEFAULT(N'1.0.0') WITH VALUES;
END;
GO

IF COL_LENGTH(N'dbo.ImageBatch', N'MetricsEligible') IS NULL
BEGIN
    ALTER TABLE dbo.ImageBatch
        ADD MetricsEligible bit NOT NULL
            CONSTRAINT DF_ImageBatch_MetricsEligible DEFAULT(0) WITH VALUES;
END;
GO

CREATE OR ALTER VIEW dbo.vw_PredictionHistoryAll AS
SELECT b.BatchID,b.ImageHash,b.OriginalFileName AS ImageName,b.StoredFileName,b.ImageRelativePath,b.ImageUrl,
 b.ProcessedFileName,b.ProcessedImageRelativePath,b.ProcessedImageUrl,
 b.ActualClass,b.OriginalWidth,b.OriginalHeight,b.Brightness,b.Contrast,b.BlurScore,b.DetectedAt,b.CompletedAt,
 b.ProcessingStatus,b.ProcessingMilliseconds,b.IsDuplicate,b.PipelineVersion,b.MetricsEligible,
 b.ErrorMessage AS BatchErrorMessage,
 p.PredictionID,m.ModelID,m.ModelKey,m.ModelName,m.Framework,m.Architecture,m.ModelVersion,m.DeploymentStage,
 m.IsEnabled,m.IsTrained,m.IsVerified,m.ValidationAccuracy,m.TestAccuracy,p.PredictedClass,p.Confidence,
 p.SecondClass,p.SecondConfidence,p.ThirdClass,p.ThirdConfidence,p.ConfidenceMargin,p.IsCorrect,p.IsUncertain,
 p.InferenceMilliseconds,p.PredictionStatus,p.ErrorMessage AS PredictionErrorMessage,p.CreatedAt,
 CASE WHEN p.PredictionStatus=N'Failed' THEN N'Failed' WHEN p.IsCorrect=1 THEN N'Correct'
      WHEN p.IsCorrect=0 THEN N'Incorrect' ELSE N'Unlabelled' END AS ResultStatus
FROM dbo.ImageBatch b
JOIN dbo.ModelPrediction p ON p.BatchID=b.BatchID
JOIN dbo.ModelRegistry m ON m.ModelID=p.ModelID;
GO

CREATE OR ALTER VIEW dbo.vw_PredictionDetail AS
SELECT *
FROM dbo.vw_PredictionHistoryAll
WHERE MetricsEligible=1;
GO

CREATE OR ALTER VIEW dbo.vw_LatestCompletedImage AS
SELECT TOP(1) b.BatchID,b.OriginalFileName AS ImageName,b.StoredFileName,b.ImageUrl,b.ImageRelativePath,
 b.ProcessedFileName,b.ProcessedImageRelativePath,b.ProcessedImageUrl,
 b.ActualClass,b.DetectedAt,b.CompletedAt,b.ProcessingStatus,b.ProcessingMilliseconds,
 b.PipelineVersion
FROM dbo.ImageBatch b
WHERE b.ProcessingStatus IN(N'Completed',N'PartialSuccess')
 AND b.StoredFileName IS NOT NULL
 AND b.MetricsEligible=1
ORDER BY COALESCE(b.CompletedAt,b.DetectedAt) DESC,b.BatchID DESC;
GO
