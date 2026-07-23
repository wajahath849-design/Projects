# Installation Guide

## Requirements

- Python 3.11+
- Docker Desktop
- PostgreSQL
- Git
- Power BI Desktop (Optional)

## Clone Repository

```bash
git clone https://github.com/yourusername/inventory-replenishment-system.git
cd inventory-replenishment-system
```

## Create Virtual Environment

```bash
python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux/Mac

```bash
source .venv/bin/activate
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Configure Environment

Copy `.env.example` to `.env` and update the database credentials.

## Start Services

```bash
docker compose up -d
```

## Load Demo Data

```bash
python scripts/load_demo.py
```

## Run API

```bash
uvicorn app.api:app --reload
```

Open Swagger:

http://localhost:8000/docs

Refresh your Power BI dashboard after the API and database are running.
