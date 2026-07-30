# Installing Colab model exports

1. Stop the API and watcher with `STOP_PROJECT.bat`.
2. Copy the six required model files into `models` using the exact filenames in `models/PLACE_TRAINED_MODELS_HERE.md`.
3. Copy their metadata JSON files into `models/metadata`.
4. Run `REGISTER_MODELS.bat`.
5. Confirm that it reports six enabled models and that `VERIFY_PROJECT.bat` passes.
6. Start the system with `START_PROJECT.bat`.

`REGISTER_MODELS.bat` does not rebuild or erase the database. The registry is synchronised during verification and service startup.

The three custom model slots are optional. Add their files and verified metadata
only when those models have been trained and evaluated.
