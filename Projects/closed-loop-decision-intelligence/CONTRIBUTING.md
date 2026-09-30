# Contributing

Use Python 3.12 and install `requirements.lock` in a virtual environment. Run
`python scripts/configure.py` once to create local credentials. Keep `.env`, database
files, logs and generated exports out of commits.

## Checks

Run these commands with the virtual environment activated:

```sh
python -m pip check
python -m ruff check src api scripts tests
python -m pytest
dbt parse --project-dir dbt --profiles-dir dbt
docker compose config --quiet
```

The PostgreSQL test is opt-in locally. Set `TEST_DATABASE_URL` to an isolated
PostgreSQL database before running it. The test creates warehouse tables and the
ledger view; never point it at a production database. GitHub Actions supplies an
ephemeral PostgreSQL service and also runs `dbt build` on that initialized schema.
This checks SQL compatibility and model tests on an empty warehouse; it does not
replace the populated end-to-end demo or n8n import checks.

For analytical changes, run the offline pipeline and evaluation described in the
README. Explain changes to alert counts, denominators, forecast assumptions and
impact calculations. Keep simulation labels isolated from analytical inputs.

## Changes

Keep pull requests focused and include the problem, resulting behavior and checks
executed. Preserve explicit approval, action idempotency and the decision audit
trail. Record incomplete runtime checks in the validation documentation.
