# Workflow operating contract

See [the import and configuration guide](../n8n/README.md) for all eleven workflows.

Stage webhooks require Header Auth. HTTP service calls use the environment-provided
analytics token, time out after five minutes, retry three times, and stop on errors.
The human approval token is never supplied to n8n. Approval polling only observes
already-approved decisions and excludes recommendations with an existing action.

The warehouse is the system of record. Workflow-local execution state is disposable;
API requests return durable record IDs. Deterministic source IDs, anomaly IDs and
unique action keys protect retries. A critical quality exception stops the chain
before KPI refresh or alert creation. Scoped tracking warnings continue with
transactional signals while suppressing misleading conversion interpretation.

Audit rows distinguish the initial run, retries, successes and failures. Pipeline and
workflow audit tables describe the same stage runs and should not be summed together.
Stage completion does not imply that downstream asynchronous webhook execution has
already completed. Inspect each downstream workflow or its warehouse audit status.

Schedule: initial ingestion daily, approval and incomplete impact checks every five
minutes. Historical demo data is loaded once; scheduling does not pretend to ingest
live systems. The explicit source-advance endpoint creates seven simulated days after
an approved rollback. A production feed would instead await real post-action data.

This build validates JSON structure and API contracts. Import, credential selection,
activation, webhooks and scheduling still require an actual n8n runtime test.
