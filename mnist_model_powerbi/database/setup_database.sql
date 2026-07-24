IF DB_ID('MNISTAnalytics') IS NULL
BEGIN
    CREATE DATABASE MNISTAnalytics;
END;
GO

USE MNISTAnalytics;
GO

IF OBJECT_ID('dbo.CustomImagePredictions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.CustomImagePredictions
    (
        PredictionID BIGINT IDENTITY(1,1) PRIMARY KEY,

        BatchID UNIQUEIDENTIFIER NOT NULL,

        ImageName NVARCHAR(255) NOT NULL,
        OriginalImagePath NVARCHAR(1000) NULL,
        ProcessedImagePath NVARCHAR(1000) NULL,

        ModelName NVARCHAR(50) NOT NULL,

        ActualDigit INT NULL,
        PredictedDigit INT NOT NULL,

        Confidence FLOAT NOT NULL,
        ConfidencePercentage FLOAT NOT NULL,

        SecondPrediction INT NULL,
        SecondConfidence FLOAT NULL,
        SecondConfidencePercentage FLOAT NULL,

        CorrectPrediction BIT NULL,
        PredictionStatus NVARCHAR(30) NOT NULL,

        ProbabilityDigit0 FLOAT NULL,
        ProbabilityDigit1 FLOAT NULL,
        ProbabilityDigit2 FLOAT NULL,
        ProbabilityDigit3 FLOAT NULL,
        ProbabilityDigit4 FLOAT NULL,
        ProbabilityDigit5 FLOAT NULL,
        ProbabilityDigit6 FLOAT NULL,
        ProbabilityDigit7 FLOAT NULL,
        ProbabilityDigit8 FLOAT NULL,
        ProbabilityDigit9 FLOAT NULL,

        OriginalWidth INT NULL,
        OriginalHeight INT NULL,
        ProcessedWidth INT NOT NULL
            CONSTRAINT DF_CustomImagePredictions_ProcessedWidth
            DEFAULT 28,
        ProcessedHeight INT NOT NULL
            CONSTRAINT DF_CustomImagePredictions_ProcessedHeight
            DEFAULT 28,

        PredictionTime DATETIME2 NOT NULL
            CONSTRAINT DF_CustomImagePredictions_PredictionTime
            DEFAULT SYSDATETIME(),

        CreatedAt DATETIME2 NOT NULL
            CONSTRAINT DF_CustomImagePredictions_CreatedAt
            DEFAULT SYSDATETIME()
    );
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CustomImagePredictions_PredictionTime'
      AND object_id =
          OBJECT_ID('dbo.CustomImagePredictions')
)
BEGIN
    CREATE INDEX IX_CustomImagePredictions_PredictionTime
        ON dbo.CustomImagePredictions(PredictionTime DESC);
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_CustomImagePredictions_ModelName'
      AND object_id =
          OBJECT_ID('dbo.CustomImagePredictions')
)
BEGIN
    CREATE INDEX IX_CustomImagePredictions_ModelName
        ON dbo.CustomImagePredictions(ModelName);
END;
GO

CREATE OR ALTER VIEW dbo.vw_LatestPredictions
AS
WITH RankedPredictions AS
(
    SELECT
        *,
        ROW_NUMBER() OVER
        (
            PARTITION BY ModelName
            ORDER BY PredictionTime DESC, PredictionID DESC
        ) AS PredictionRank
    FROM dbo.CustomImagePredictions
)
SELECT
    PredictionID,
    BatchID,
    ImageName,
    OriginalImagePath,
    ProcessedImagePath,
    ModelName,
    ActualDigit,
    PredictedDigit,
    Confidence,
    ConfidencePercentage,
    SecondPrediction,
    SecondConfidencePercentage,
    CorrectPrediction,
    PredictionStatus,
    PredictionTime
FROM RankedPredictions
WHERE PredictionRank = 1;
GO

CREATE OR ALTER VIEW dbo.vw_PredictionSummary
AS
SELECT
    ModelName,
    COUNT(*) AS TotalPredictions,
    SUM
    (
        CASE
            WHEN CorrectPrediction = 1 THEN 1
            ELSE 0
        END
    ) AS CorrectPredictions,
    SUM
    (
        CASE
            WHEN CorrectPrediction = 0 THEN 1
            ELSE 0
        END
    ) AS IncorrectPredictions,
    AVG(ConfidencePercentage) AS AverageConfidencePercentage,
    MAX(PredictionTime) AS LatestPredictionTime
FROM dbo.CustomImagePredictions
GROUP BY ModelName;
GO