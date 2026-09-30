# n8n control plane

The eleven JSON files implement separate callable workflows. Python and dbt own
calculations; n8n owns triggering, retries, handoffs, waits and the approval gate.
All workflows import **inactive**. Runtime import/execution must be checked against
the pinned n8n image after Docker is available; JSON contract tests are not a runtime test.

## Import and credentials

1. Run `docker compose up -d --build`; open http://localhost:5678 and create the local owner.
2. Create a **Header Auth** credential named **CLDI Workflow Header**. Header name:
   `X-Workflow-Key`; value: the `API_TOKEN` from your local `.env`.
3. Import the eleven workflow JSON files using the n8n UI, or run:
   `docker compose exec -u node n8n n8n import:workflow --separate --input=/workflows`.
4. Open each workflow's **Authenticated stage webhook** node and select that credential.
5. Activate all eleven workflows. Their paths are `cldi-ingestion`, `cldi-quality`,
   `cldi-kpis`, `cldi-anomalies`, `cldi-investigation`, `cldi-forecast`, `cldi-decisions`,
   `cldi-approvals`, `cldi-actions`, `cldi-impact`, and `cldi-memory`.
6. Manually execute workflow 01 for the initial run. Source ingestion refuses to merge
   different generated datasets; subsequent scheduled ingestion observes the existing feed.

Compose provides `ANALYTICS_API_URL` and `ANALYTICS_API_TOKEN`. Environment access
inside nodes is enabled for this single-user local instance. Do not grant untrusted
users workflow-editing access. For shared deployments, use managed credentials and
restrict environment access. n8n never receives the separate `APPROVAL_TOKEN`.

## Workflow behavior

| Workflow | Work | Handoff / stop |
|---|---|---|
| 01 Data ingestion | Deterministic sources, atomic load, audit | 02; scheduled daily |
| 02 Quality | Source integrity and independent tracking reconciliation | Failure stops HTTP node; pass starts 03 |
| 03 KPI | dbt build/tests, configured KPI calculations | 04 |
| 04 Detector | Seven-method ensemble, coalesced incidents | 05 |
| 05 Investigation | Contributions and temporal hypotheses | 06 |
| 06 Forecast | Current incidents, 7/30-day risk | 07 |
| 07 Decision | Rules, evidence references, memory, pending approval | 08 |
| 08 Human approval | Polls decisions actually approved through FastAPI | IF approved starts 09; otherwise stops; polls every five minutes |
| 09 Action | Idempotent simulation; advance seven synthetic post-action days | One-minute wait; 10 |
| 10 Impact | Verify complete windows and compute effect | Returns WAITING_FOR_DATA when incomplete; retries on schedule; 11 |
| 11 Memory | Ledger and closed-outcome readout | Completes; no external messages are sent |

Human approval: open FastAPI `/docs`, call
`POST /recommendations/{id}/approve` with `X-API-Key`, the separate
`X-Approval-Token`, and `{"actor":"your-name"}`. Reject uses the same headers plus
a reason. Names are operator assertions in this local demo, not authenticated SSO identities.
The n8n service token cannot approve a recommendation by itself.

Every analytical stage writes `monitoring.pipeline_runs` and `audit.workflow_runs`.
HTTP failures prevent downstream handoff; nodes retry up to three times. The API
keeps the durable state, so repeated n8n delivery cannot execute an action twice.
Source advancement is an explicit simulator operation: one minute does not represent
seven elapsed real-world days. The CLI demo uses the same services but does not claim
to be an n8n execution.

Version references: [n8n source and releases](https://github.com/n8n-io/n8n),
[dbt PostgreSQL setup](https://docs.getdbt.com/docs/local/connect-data-platform/postgres-setup).
