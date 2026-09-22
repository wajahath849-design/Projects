@echo off
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e ".[dev]"
if not exist .env copy .env.example .env
echo Environment ready. Update .env before running the ETL.
