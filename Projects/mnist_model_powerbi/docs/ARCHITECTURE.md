# Final architecture

```text
Image copied to data/incoming
        |
        v
File stability + SHA-256 duplicate check
        |
        v
One ImageBatch row
        |
        +--> enabled verified model 1 --> ModelPrediction + 10 probabilities
        +--> enabled verified model 2 --> ModelPrediction + 10 probabilities
        +--> ...
        +--> enabled verified model 9 --> ModelPrediction + 10 probabilities
        |
        v
Completed / PartialSuccess / Failed / Duplicate
        |
        +--> SQL reporting views --> Power BI
        +--> FastAPI image and feedback endpoints
```

Every model is isolated. One model failure does not stop the others. The database retains all metadata, while the image retention policy keeps only the newest display image by default.
