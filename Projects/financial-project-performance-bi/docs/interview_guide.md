# Interview preparation guide

Use the project files and synthetic results to support each answer; avoid describing fictional outcomes as work for a real company.

1. **Why is budget a separate fact?** It has project-version-department grain, unlike dated transactions; joining it directly to costs would multiply allocations.
2. **How is the approved budget selected?** Latest approved date by project as of the reporting date, with version number as a tie-breaker.
3. **Why keep older budget versions?** They support an approval timeline and audit trail without being included in the current approved total.
4. **Why is a positive budget variance favorable?** The convention is budget minus actual; a negative result means actual spend exceeded approval.
5. **Why can portfolio budget variance look favorable while many projects overrun?** Underspends offset overspends in the net sum, so project counts and summed positive overruns are shown separately.
6. **How are negative cost rows treated?** Valid corrections are retained as signed transactions; only malformed or invalid-reference rows are quarantined.
7. **How does the ETL avoid duplicate loads?** It rebuilds curated outputs from source, removes duplicate business IDs, and tests identical output hashes on rerun.
8. **What metadata makes a refresh auditable?** Source path, SHA-256, byte size, row count, rejected rows and reasons, and reconciliation deltas.
9. **How would you investigate an unfamiliar cost spike?** Compare monthly run rate, filter department/category, inspect transaction IDs, then validate source posting and project scope.
10. **Why distinguish revenue from cash?** `FactRevenue` records recognized revenue; invoice and receipt events are absent, so cash claims would be unsupported.
11. **What is the difference between gross profit and margin?** Profit is dollars of revenue less cost; margin divides that profit by revenue.
12. **Why are weighted and average project margins different?** Weighted margin uses total profit/total revenue; average project margin gives each project equal weight.
13. **Why remove the date filter from lifetime DAX?** A project lifetime budget would otherwise be compared against only part of its actual cost when a month slicer is used.
14. **How is a monthly budget trend constructed?** Pick the latest approved version as of each axis date, rather than summing all revision rows.
15. **What relationships should Power BI use?** One-to-many, single direction from dimensions to facts, with no second active path through budget version.
16. **How does the forecast avoid leakage?** Each snapshot's trailing rate uses only monthly actuals through its snapshot date; a test changes later data and checks June forecasts stay identical.
17. **What does ETC mean?** The forecasted future cost after the snapshot; EAC adds observed lifetime actual cost.
18. **What would make the forecast misleading?** Schedule slips, staff changes, procurement commitments, or changed scope are absent from the simple rate model.
19. **How was forecast error evaluated?** June snapshot predictions were compared with observed later monthly costs, with absolute error reported per project.
20. **Why use three forecast scenarios?** They expose sensitivity to future burn rate assumptions without implying precise probability estimates.
21. **What does the synthetic data intentionally test?** Duplicate ID, missing project, invalid category, invalid date, negative corrections, version changes, and three financial scenarios.
22. **How would SQL independently verify the model?** Load curated CSVs into SQLite, query `v_project_financials`, and compare portfolio totals with the Python extract.
23. **What does the Power Query function do?** It reads each curated CSV from a configurable folder, promotes headers, and applies explicit data types.
24. **How would you extend this to multiple currencies?** Add dated FX rates, normalize each posting at the appropriate rate, retain source currency, and reconcile both source and reporting amounts.
25. **What would you add for production deployment?** Governed source contracts, incremental refresh where justified, ownership for exceptions, access controls, change management, and monitoring of forecast drift.

