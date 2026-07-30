# Recommended Power BI pages

## Page 1 — Executive Overview
- Total images
- CNN accuracy
- Neural Network accuracy
- Average confidence
- Latest prediction time
- Average processing time

## Page 2 — Live Prediction
Use `vw_LatestPredictions`.
- Image name
- Model
- Predicted digit
- Confidence percentage
- Actual digit
- Status
- Prediction time

## Page 3 — Prediction History
Use `CustomImagePredictions`.
- Table with image, model, actual, predicted, confidence, status, time
- Model slicer
- Digit slicers
- Date filter

## Page 4 — Confusion Matrix
Use `vw_ConfusionMatrix`.
- Matrix rows: ActualDigit
- Matrix columns: PredictedDigit
- Values: PredictionCount

## Page 5 — Model Comparison
- Accuracy
- Error count
- Average confidence
- Processing time
- Prediction distribution
