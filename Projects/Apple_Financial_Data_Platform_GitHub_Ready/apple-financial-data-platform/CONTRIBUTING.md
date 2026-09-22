# Contributing

1. Create a feature branch.
2. Keep SEC calls out of automated tests; use fixtures.
3. Add or update tests for transformation changes.
4. Run `ruff check src tests` and `pytest`.
5. Do not commit `.env`, credentials, raw SEC downloads or database backups.
6. Explain any new XBRL tag mapping in the pull request.
