.PHONY: install verify test lint sample-pipeline inventory optimize scenarios api powerbi project-verify

install:
	python -m pip install -r requirements.txt -r requirements-dev.txt

verify:
	python scripts/verify_environment.py

test:
	python -m pytest -p no:cacheprovider --basetemp .pytest-tmp

lint:
	python -m ruff check .
	python -m mypy src

sample-pipeline:
	python scripts/build_features.py
	python scripts/train_models.py
	python scripts/generate_forecasts.py
	python scripts/generate_explanations.py

inventory:
	python scripts/calculate_inventory_intelligence.py

optimize:
	python scripts/run_optimization.py

scenarios:
	python scripts/run_scenarios.py

api:
	uvicorn decision_intelligence.api.main:app --reload

powerbi:
	python scripts/export_power_bi_data.py

project-verify:
	python scripts/verify_project.py
