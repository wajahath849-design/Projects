.PHONY: install migrate test lint dev docker-up docker-down

install:
	python -m pip install -r backend/requirements-dev.txt
	cd frontend && npm install

migrate:
	cd backend && python manage.py migrate

test:
	cd backend && python -m pytest
	cd frontend && npm test

lint:
	cd backend && ruff check .
	cd frontend && npm run build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

