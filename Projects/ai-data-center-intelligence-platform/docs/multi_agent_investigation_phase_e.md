# Phase E — Selective Multi-Analyst Investigation

The investigation coordinator keeps simple cases on a deterministic two-analyst
route and invokes log/alert, historical, and maintenance specialists only when
critical or multi-domain evidence makes the case complex. Each finding uses a
deduplicated, database-backed evidence ID. Major claims fail closed unless the
referenced IDs exist.

The final report exposes analyst names and findings, never private reasoning.
Its confidence vocabulary is `LIKELY`, `POSSIBLE`, or
`INSUFFICIENT_EVIDENCE`; it is qualitative, not a probability. Historical
analogues disclose their limited matching basis, log text remains untrusted
data, recommendations require human approval, and the investigation code has
no access to private scenario truth.
