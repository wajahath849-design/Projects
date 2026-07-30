IF DB_ID(N'AIModelAnalytics') IS NULL CREATE DATABASE AIModelAnalytics;
GO
USE AIModelAnalytics;
GO

DECLARE @views nvarchar(max)=N'';
SELECT @views += N'DROP VIEW '+QUOTENAME(SCHEMA_NAME(schema_id))+N'.'+QUOTENAME(name)+N';'+CHAR(10)
FROM sys.views WHERE schema_id=SCHEMA_ID(N'dbo');
IF @views<>N'' EXEC sys.sp_executesql @views;
GO
DROP TABLE IF EXISTS dbo.ClassProbability;
DROP TABLE IF EXISTS dbo.HumanReview;
DROP TABLE IF EXISTS dbo.ModelPrediction;
DROP TABLE IF EXISTS dbo.SystemEvent;
DROP TABLE IF EXISTS dbo.LatestDetectedImage;
DROP TABLE IF EXISTS dbo.PredictionBatch;
DROP TABLE IF EXISTS dbo.ImageBatch;
DROP TABLE IF EXISTS dbo.ModelRegistry;
GO

CREATE TABLE dbo.ModelRegistry(
 ModelID int IDENTITY(1,1) CONSTRAINT PK_ModelRegistry PRIMARY KEY,
 ModelKey nvarchar(100) NOT NULL CONSTRAINT UQ_ModelRegistry_ModelKey UNIQUE,
 ModelName nvarchar(150) NOT NULL, Framework nvarchar(40) NOT NULL,
 Architecture nvarchar(120) NOT NULL, ModelVersion nvarchar(50) NOT NULL,
 ModelPath nvarchar(500) NOT NULL, DatasetName nvarchar(100) NOT NULL,
 InputWidth smallint NOT NULL, InputHeight smallint NOT NULL, InputChannels tinyint NOT NULL,
 DeploymentStage nvarchar(30) NOT NULL, IsEnabled bit NOT NULL CONSTRAINT DF_ModelRegistry_Enabled DEFAULT(0),
 IsTrained bit NOT NULL CONSTRAINT DF_ModelRegistry_Trained DEFAULT(0),
 IsVerified bit NOT NULL CONSTRAINT DF_ModelRegistry_Verified DEFAULT(0),
 ValidationAccuracy decimal(9,6) NULL, TestAccuracy decimal(9,6) NULL, TrainingDate datetime2(0) NULL,
 CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_ModelRegistry_Created DEFAULT SYSUTCDATETIME(),
 UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_ModelRegistry_Updated DEFAULT SYSUTCDATETIME(),
 CONSTRAINT CK_ModelRegistry_Input CHECK(InputWidth>0 AND InputHeight>0 AND InputChannels IN(1,3)),
 CONSTRAINT CK_ModelRegistry_ValAcc CHECK(ValidationAccuracy IS NULL OR ValidationAccuracy BETWEEN 0 AND 1),
 CONSTRAINT CK_ModelRegistry_TestAcc CHECK(TestAccuracy IS NULL OR TestAccuracy BETWEEN 0 AND 1)
);
GO

CREATE TABLE dbo.ImageBatch(
 BatchID uniqueidentifier CONSTRAINT PK_ImageBatch PRIMARY KEY,
 ImageHash char(64) NOT NULL, OriginalFileName nvarchar(255) NOT NULL,
 StoredFileName nvarchar(300) NULL, ImageRelativePath nvarchar(600) NULL, ImageUrl nvarchar(1000) NULL,
 ProcessedFileName nvarchar(300) NULL, ProcessedImageRelativePath nvarchar(600) NULL,
 ProcessedImageUrl nvarchar(1000) NULL,
 ActualClass nvarchar(50) NULL, OriginalWidth int NULL, OriginalHeight int NULL,
 Brightness decimal(12,3) NULL, Contrast decimal(12,3) NULL, BlurScore decimal(18,3) NULL,
 DetectedAt datetime2(3) NOT NULL CONSTRAINT DF_ImageBatch_Detected DEFAULT SYSUTCDATETIME(),
 CompletedAt datetime2(3) NULL, ProcessingStatus nvarchar(30) NOT NULL,
 ProcessingMilliseconds decimal(18,3) NULL, IsDuplicate bit NOT NULL CONSTRAINT DF_ImageBatch_Duplicate DEFAULT(0),
 DuplicateOfBatchID uniqueidentifier NULL, ErrorMessage nvarchar(4000) NULL,
 PipelineVersion nvarchar(30) NOT NULL CONSTRAINT DF_ImageBatch_PipelineVersion DEFAULT(N'2.0.0'),
 MetricsEligible bit NOT NULL CONSTRAINT DF_ImageBatch_MetricsEligible DEFAULT(1),
 CONSTRAINT FK_ImageBatch_Duplicate FOREIGN KEY(DuplicateOfBatchID) REFERENCES dbo.ImageBatch(BatchID),
 CONSTRAINT CK_ImageBatch_Status CHECK(ProcessingStatus IN(N'Processing',N'Completed',N'PartialSuccess',N'Failed',N'Duplicate'))
);
GO
CREATE UNIQUE INDEX UX_ImageBatch_UniqueHash ON dbo.ImageBatch(ImageHash) WHERE IsDuplicate=0 AND ProcessingStatus<>N'Failed';
CREATE INDEX IX_ImageBatch_Recent ON dbo.ImageBatch(DetectedAt DESC) INCLUDE(ProcessingStatus,ImageUrl,ActualClass,CompletedAt);
CREATE INDEX IX_ImageBatch_Status ON dbo.ImageBatch(ProcessingStatus,DetectedAt DESC);
GO

CREATE TABLE dbo.ModelPrediction(
 PredictionID bigint IDENTITY(1,1) CONSTRAINT PK_ModelPrediction PRIMARY KEY,
 BatchID uniqueidentifier NOT NULL, ModelID int NOT NULL,
 PredictedClass nvarchar(50) NULL, Confidence decimal(12,10) NULL,
 SecondClass nvarchar(50) NULL, SecondConfidence decimal(12,10) NULL,
 ThirdClass nvarchar(50) NULL, ThirdConfidence decimal(12,10) NULL,
 ConfidenceMargin decimal(12,10) NULL, IsCorrect bit NULL, IsUncertain bit NULL,
 InferenceMilliseconds decimal(18,3) NULL, PredictionStatus nvarchar(20) NOT NULL,
 ErrorMessage nvarchar(4000) NULL, CreatedAt datetime2(3) NOT NULL CONSTRAINT DF_ModelPrediction_Created DEFAULT SYSUTCDATETIME(),
 CONSTRAINT FK_ModelPrediction_Batch FOREIGN KEY(BatchID) REFERENCES dbo.ImageBatch(BatchID) ON DELETE CASCADE,
 CONSTRAINT FK_ModelPrediction_Model FOREIGN KEY(ModelID) REFERENCES dbo.ModelRegistry(ModelID),
 CONSTRAINT UQ_ModelPrediction_BatchModel UNIQUE(BatchID,ModelID),
 CONSTRAINT CK_ModelPrediction_Status CHECK(PredictionStatus IN(N'Succeeded',N'Failed',N'Skipped')),
 CONSTRAINT CK_ModelPrediction_Confidence CHECK(Confidence IS NULL OR Confidence BETWEEN 0 AND 1)
);
GO
CREATE INDEX IX_ModelPrediction_ModelRecent ON dbo.ModelPrediction(ModelID,CreatedAt DESC);
CREATE INDEX IX_ModelPrediction_BatchStatus ON dbo.ModelPrediction(BatchID,PredictionStatus);
GO

CREATE TABLE dbo.ClassProbability(
 PredictionID bigint NOT NULL, ClassLabel nvarchar(50) NOT NULL, Probability decimal(12,10) NOT NULL,
 CONSTRAINT PK_ClassProbability PRIMARY KEY(PredictionID,ClassLabel),
 CONSTRAINT FK_ClassProbability_Prediction FOREIGN KEY(PredictionID) REFERENCES dbo.ModelPrediction(PredictionID) ON DELETE CASCADE,
 CONSTRAINT CK_ClassProbability_Value CHECK(Probability BETWEEN 0 AND 1)
);
GO

CREATE TABLE dbo.HumanReview(
 ReviewID bigint IDENTITY(1,1) CONSTRAINT PK_HumanReview PRIMARY KEY,
 BatchID uniqueidentifier NOT NULL, CorrectedClass nvarchar(50) NOT NULL,
 Reviewer nvarchar(150) NULL, Notes nvarchar(1000) NULL,
 ReviewedAt datetime2(3) NOT NULL CONSTRAINT DF_HumanReview_Reviewed DEFAULT SYSUTCDATETIME(),
 CONSTRAINT FK_HumanReview_Batch FOREIGN KEY(BatchID) REFERENCES dbo.ImageBatch(BatchID) ON DELETE CASCADE
);
GO
CREATE INDEX IX_HumanReview_BatchRecent ON dbo.HumanReview(BatchID,ReviewedAt DESC);
GO

CREATE TABLE dbo.SystemEvent(
 EventID bigint IDENTITY(1,1) CONSTRAINT PK_SystemEvent PRIMARY KEY,
 EventTime datetime2(3) NOT NULL CONSTRAINT DF_SystemEvent_Time DEFAULT SYSUTCDATETIME(),
 Severity nvarchar(20) NOT NULL, Component nvarchar(100) NOT NULL,
 EventCode nvarchar(80) NULL, Message nvarchar(4000) NOT NULL,
 BatchID uniqueidentifier NULL, ModelID int NULL,
 CONSTRAINT FK_SystemEvent_Batch FOREIGN KEY(BatchID) REFERENCES dbo.ImageBatch(BatchID) ON DELETE SET NULL,
 CONSTRAINT FK_SystemEvent_Model FOREIGN KEY(ModelID) REFERENCES dbo.ModelRegistry(ModelID),
 CONSTRAINT CK_SystemEvent_Severity CHECK(Severity IN(N'Debug',N'Information',N'Warning',N'Error',N'Critical'))
);
GO
CREATE INDEX IX_SystemEvent_Recent ON dbo.SystemEvent(EventTime DESC) INCLUDE(Severity,Component,EventCode);
GO
