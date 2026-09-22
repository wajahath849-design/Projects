.PHONY: install test lint init-db run csv validate export sql-up sql-down

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

sql-up:
	docker compose up -d

sql-down:
	docker compose down

init-db:
	apple-finance-etl init-db

run:
	apple-finance-etl run

csv:
	apple-finance-etl run --csv-only

validate:
	apple-finance-etl validate data/sample/offline_sample_financial_facts.csv

export:
	apple-finance-etl export
