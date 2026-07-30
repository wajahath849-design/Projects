USE AIModelAnalytics;
GO

IF COL_LENGTH(N'dbo.ImageBatch', N'ProcessedFileName') IS NULL
    ALTER TABLE dbo.ImageBatch ADD ProcessedFileName nvarchar(300) NULL;
GO
IF COL_LENGTH(N'dbo.ImageBatch', N'ProcessedImageRelativePath') IS NULL
    ALTER TABLE dbo.ImageBatch ADD ProcessedImageRelativePath nvarchar(600) NULL;
GO
IF COL_LENGTH(N'dbo.ImageBatch', N'ProcessedImageUrl') IS NULL
    ALTER TABLE dbo.ImageBatch ADD ProcessedImageUrl nvarchar(1000) NULL;
GO

CREATE OR ALTER VIEW dbo.vw_PredictionDetail AS
SELECT b.BatchID,b.ImageHash,b.OriginalFileName AS ImageName,b.StoredFileName,b.ImageRelativePath,b.ImageUrl,
 b.ProcessedFileName,b.ProcessedImageRelativePath,b.ProcessedImageUrl,
 b.ActualClass,b.OriginalWidth,b.OriginalHeight,b.Brightness,b.Contrast,b.BlurScore,b.DetectedAt,b.CompletedAt,
 b.ProcessingStatus,b.ProcessingMilliseconds,b.IsDuplicate,b.ErrorMessage AS BatchErrorMessage,
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

CREATE OR ALTER VIEW dbo.vw_LatestCompletedImage AS
SELECT TOP(1) b.BatchID,b.OriginalFileName AS ImageName,b.StoredFileName,b.ImageUrl,b.ImageRelativePath,
 b.ProcessedFileName,b.ProcessedImageRelativePath,b.ProcessedImageUrl,
 b.ActualClass,b.DetectedAt,b.CompletedAt,b.ProcessingStatus,b.ProcessingMilliseconds
FROM dbo.ImageBatch b
WHERE b.ProcessingStatus IN(N'Completed',N'PartialSuccess') AND b.StoredFileName IS NOT NULL
ORDER BY COALESCE(b.CompletedAt,b.DetectedAt) DESC,b.BatchID DESC;
GO
