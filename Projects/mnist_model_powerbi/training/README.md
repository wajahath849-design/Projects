# Google Colab training output contract

Train all models using the shared MNIST split and export the files listed in `models/PLACE_TRAINED_MODELS_HERE.md`.

The installed Keras artifacts accept raw `0..255` `28x28x1` pixels because their saved graphs already contain rescaling or application preprocessing layers. Set `input_range: 0_255` in `config/models.yml` for these models. Do not divide by 255 in both the application and the model. PyTorch and ONNX use the input range declared in their model configuration and are converted to NCHW by their adapters.

Each metadata JSON must contain at minimum:

```json
{
  "model_key": "cnn",
  "trained": true,
  "verified": true,
  "validation_accuracy": 0.99,
  "test_accuracy": 0.99,
  "model_version": "1.0.0"
}
```
