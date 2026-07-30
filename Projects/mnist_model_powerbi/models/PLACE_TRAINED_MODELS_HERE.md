# Required trained model files

Copy these six required files into this `models` folder:

- `neural_network.keras`
- `cnn.keras`
- `mobilenet_v2.keras`
- `resnet50.keras`
- `efficientnet_b0.keras`
- `vision_transformer.keras`

Copy matching JSON metadata into `models/metadata`:

- `neural_network.json`
- `cnn.json`
- `mobilenet_v2.json`
- `resnet50.json`
- `efficientnet_b0.json`
- `vision_transformer.json`

Then run `REGISTER_MODELS.bat`. Only models with validation and test accuracy of at
least 90% and `verified: true` are enabled.

Optional custom model slots:

- `custom_keras.keras`
- `custom_pytorch.pt` (TorchScript, not a raw state dictionary)
- `custom_model.onnx`

Their matching metadata files are `custom_keras.json`, `custom_pytorch.json`, and
`custom_onnx.json`.
