USE AIModelAnalytics;
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
FROM dbo.ImageBatch b JOIN dbo.ModelPrediction p ON p.BatchID=b.BatchID JOIN dbo.ModelRegistry m ON m.ModelID=p.ModelID;
GO

CREATE OR ALTER VIEW dbo.vw_PredictionDetail AS
SELECT *
FROM dbo.vw_PredictionHistoryAll
WHERE MetricsEligible=1;
GO

CREATE OR ALTER VIEW dbo.vw_LatestCompletedImage AS
SELECT TOP(1) b.BatchID,b.OriginalFileName AS ImageName,b.StoredFileName,b.ImageUrl,b.ImageRelativePath,
 b.ProcessedFileName,b.ProcessedImageRelativePath,b.ProcessedImageUrl,
 b.ActualClass,b.DetectedAt,b.CompletedAt,b.ProcessingStatus,b.ProcessingMilliseconds
FROM dbo.ImageBatch b
WHERE b.ProcessingStatus IN(N'Completed',N'PartialSuccess') AND b.StoredFileName IS NOT NULL
 AND b.MetricsEligible=1
ORDER BY COALESCE(b.CompletedAt,b.DetectedAt) DESC,b.BatchID DESC;
GO

CREATE OR ALTER VIEW dbo.vw_ModelAgreement AS
WITH Votes AS(
 SELECT p.BatchID,PredictedClass,COUNT_BIG(*) AS VoteCount,AVG(Confidence) AS AvgConfidence
 FROM dbo.ModelPrediction p JOIN dbo.ImageBatch b ON b.BatchID=p.BatchID
 WHERE p.PredictionStatus=N'Succeeded' AND b.MetricsEligible=1 GROUP BY p.BatchID,PredictedClass
), Ranked AS(
 SELECT *,ROW_NUMBER() OVER(PARTITION BY BatchID ORDER BY VoteCount DESC,AvgConfidence DESC,PredictedClass) AS rn FROM Votes
), Totals AS(
 SELECT p.BatchID,COUNT_BIG(*) AS SuccessfulModelCount,COUNT(DISTINCT PredictedClass) AS DistinctPredictions
 FROM dbo.ModelPrediction p JOIN dbo.ImageBatch b ON b.BatchID=p.BatchID
 WHERE p.PredictionStatus=N'Succeeded' AND b.MetricsEligible=1 GROUP BY p.BatchID
)
SELECT b.BatchID,b.OriginalFileName AS ImageName,b.ActualClass,t.SuccessfulModelCount,t.DistinctPredictions,
 r.PredictedClass AS ConsensusPrediction,r.VoteCount AS ConsensusVotes,
 CAST(1.0*r.VoteCount/NULLIF(t.SuccessfulModelCount,0) AS decimal(10,6)) AS AgreementRate
FROM dbo.ImageBatch b JOIN Totals t ON t.BatchID=b.BatchID JOIN Ranked r ON r.BatchID=b.BatchID AND r.rn=1;
GO

CREATE OR ALTER VIEW dbo.vw_LatestBatchSummary AS
SELECT TOP(1) b.BatchID,b.OriginalFileName AS ImageName,b.ImageUrl,b.ActualClass,b.ProcessingStatus,
 b.DetectedAt,b.CompletedAt,b.ProcessingMilliseconds,a.SuccessfulModelCount,a.DistinctPredictions,
 a.ConsensusPrediction,a.ConsensusVotes,a.AgreementRate
FROM dbo.ImageBatch b LEFT JOIN dbo.vw_ModelAgreement a ON a.BatchID=b.BatchID
WHERE b.ProcessingStatus IN(N'Completed',N'PartialSuccess') AND b.MetricsEligible=1
ORDER BY COALESCE(b.CompletedAt,b.DetectedAt) DESC,b.BatchID DESC;
GO

CREATE OR ALTER VIEW dbo.vw_BatchPredictionResults AS
SELECT * FROM dbo.vw_PredictionDetail WHERE PredictionStatus=N'Succeeded';
GO

CREATE OR ALTER VIEW dbo.vw_ModelPerformance AS
WITH CurrentPredictions AS(
 SELECT p.*
 FROM dbo.ModelPrediction p
 JOIN dbo.ImageBatch b ON b.BatchID=p.BatchID
 WHERE b.MetricsEligible=1
)
SELECT m.ModelID,m.ModelKey,m.ModelName,m.Framework,m.Architecture,m.ModelVersion,m.DeploymentStage,
 m.IsEnabled,m.IsTrained,m.IsVerified,m.ValidationAccuracy,m.TestAccuracy,
 COUNT_BIG(p.PredictionID) AS TotalAttempts,
 SUM(CASE WHEN p.PredictionStatus=N'Succeeded' THEN 1 ELSE 0 END) AS SuccessfulPredictions,
 SUM(CASE WHEN p.PredictionStatus=N'Failed' THEN 1 ELSE 0 END) AS FailedPredictions,
 SUM(CASE WHEN p.IsCorrect IS NOT NULL THEN 1 ELSE 0 END) AS LabelledPredictions,
 SUM(CASE WHEN p.IsCorrect=1 THEN 1 ELSE 0 END) AS CorrectPredictions,
 CAST(AVG(CASE WHEN p.IsCorrect=1 THEN 1.0 WHEN p.IsCorrect=0 THEN 0.0 END) AS decimal(10,6)) AS ObservedAccuracy,
 CAST(AVG(CASE WHEN p.PredictionStatus=N'Succeeded' THEN p.Confidence END) AS decimal(10,6)) AS AvgConfidence,
 CAST(AVG(CASE WHEN p.PredictionStatus=N'Succeeded' THEN p.InferenceMilliseconds END) AS decimal(18,3)) AS AvgInferenceMs
FROM dbo.ModelRegistry m LEFT JOIN CurrentPredictions p ON p.ModelID=m.ModelID
GROUP BY m.ModelID,m.ModelKey,m.ModelName,m.Framework,m.Architecture,m.ModelVersion,m.DeploymentStage,
 m.IsEnabled,m.IsTrained,m.IsVerified,m.ValidationAccuracy,m.TestAccuracy;
GO

CREATE OR ALTER VIEW dbo.vw_ConfusionMatrix AS
SELECT m.ModelName,b.ActualClass,p.PredictedClass,COUNT_BIG(*) AS PredictionCount
FROM dbo.ModelPrediction p JOIN dbo.ModelRegistry m ON m.ModelID=p.ModelID JOIN dbo.ImageBatch b ON b.BatchID=p.BatchID
WHERE p.PredictionStatus=N'Succeeded' AND b.ActualClass IS NOT NULL AND b.MetricsEligible=1
GROUP BY m.ModelName,b.ActualClass,p.PredictedClass;
GO

CREATE OR ALTER VIEW dbo.vw_ClassPerformance AS
SELECT m.ModelName,b.ActualClass,COUNT_BIG(*) AS LabelledPredictions,
 SUM(CASE WHEN p.IsCorrect=1 THEN 1 ELSE 0 END) AS CorrectPredictions,
 CAST(AVG(CASE WHEN p.IsCorrect=1 THEN 1.0 ELSE 0.0 END) AS decimal(10,6)) AS ClassAccuracy,
 CAST(AVG(p.Confidence) AS decimal(10,6)) AS AvgConfidence
FROM dbo.ModelPrediction p JOIN dbo.ModelRegistry m ON m.ModelID=p.ModelID JOIN dbo.ImageBatch b ON b.BatchID=p.BatchID
WHERE p.PredictionStatus=N'Succeeded' AND b.ActualClass IS NOT NULL AND b.MetricsEligible=1
GROUP BY m.ModelName,b.ActualClass;
GO

CREATE OR ALTER VIEW dbo.vw_DailyProcessingTrend AS
SELECT CAST(DetectedAt AS date) AS ProcessingDate,COUNT_BIG(*) AS TotalImages,
 SUM(CASE WHEN ProcessingStatus=N'Completed' THEN 1 ELSE 0 END) AS CompletedImages,
 SUM(CASE WHEN ProcessingStatus=N'PartialSuccess' THEN 1 ELSE 0 END) AS PartialImages,
 SUM(CASE WHEN ProcessingStatus=N'Failed' THEN 1 ELSE 0 END) AS FailedImages,
 SUM(CASE WHEN ProcessingStatus=N'Duplicate' THEN 1 ELSE 0 END) AS DuplicateImages,
 CAST(AVG(CASE WHEN ProcessingStatus IN(N'Completed',N'PartialSuccess') THEN ProcessingMilliseconds END) AS decimal(18,3)) AS AvgProcessingMs
FROM dbo.ImageBatch WHERE MetricsEligible=1 GROUP BY CAST(DetectedAt AS date);
GO

CREATE OR ALTER VIEW dbo.vw_FailedPredictions AS
SELECT BatchID,ImageName,ModelKey,ModelName,Framework,PredictionErrorMessage,CreatedAt
FROM dbo.vw_PredictionDetail WHERE PredictionStatus=N'Failed';
GO

CREATE OR ALTER VIEW dbo.vw_HumanReviewQueue AS
SELECT b.BatchID,b.OriginalFileName AS ImageName,b.ImageUrl,b.ActualClass,a.ConsensusPrediction,a.AgreementRate,b.DetectedAt,
 CASE WHEN r.ReviewID IS NULL THEN N'Pending' ELSE N'Reviewed' END AS ReviewStatus,
 r.CorrectedClass,r.Reviewer,r.ReviewedAt
FROM dbo.ImageBatch b LEFT JOIN dbo.vw_ModelAgreement a ON a.BatchID=b.BatchID
OUTER APPLY(SELECT TOP(1)* FROM dbo.HumanReview h WHERE h.BatchID=b.BatchID ORDER BY h.ReviewedAt DESC) r
WHERE b.ProcessingStatus IN(N'Completed',N'PartialSuccess') AND b.MetricsEligible=1
 AND (b.ActualClass IS NULL OR a.AgreementRate<0.6);
GO

CREATE OR ALTER VIEW dbo.vw_SystemHealth AS
SELECT COUNT_BIG(*) AS TotalImages,
 SUM(CASE WHEN ProcessingStatus=N'Completed' THEN 1 ELSE 0 END) AS CompletedImages,
 SUM(CASE WHEN ProcessingStatus=N'PartialSuccess' THEN 1 ELSE 0 END) AS PartialImages,
 SUM(CASE WHEN ProcessingStatus=N'Failed' THEN 1 ELSE 0 END) AS FailedImages,
 SUM(CASE WHEN ProcessingStatus=N'Duplicate' THEN 1 ELSE 0 END) AS DuplicateImages,
 CAST(AVG(CASE WHEN ProcessingStatus IN(N'Completed',N'PartialSuccess') THEN ProcessingMilliseconds END) AS decimal(18,3)) AS AvgProcessingMs,
 MAX(DetectedAt) AS LastDetectionAt
FROM dbo.ImageBatch WHERE MetricsEligible=1;
GO
