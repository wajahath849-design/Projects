PYTHON ?= python
.PHONY: setup up generate transform pipeline demo test evaluate lint
setup:
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) scripts/configure.py
up:
	docker compose up -d --build
generate:
	$(PYTHON) -m src.cli generate-data --months 24 --seed 42
transform:
	$(PYTHON) -m src.cli transform
pipeline:
	$(PYTHON) -m src.cli run-pipeline
demo:
	$(PYTHON) -m src.cli demo
test:
	$(PYTHON) -m pytest
evaluate:
	$(PYTHON) -m src.cli evaluate
lint:
	$(PYTHON) -m ruff check src api scripts tests
