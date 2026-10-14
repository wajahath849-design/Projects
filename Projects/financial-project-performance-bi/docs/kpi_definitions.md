# KPI definitions and checks

All examples come from the fixed-seed **synthetic demonstration data** as of 2026-09-30. Amounts are USD. `Lifetime` measures ignore the date slicer but still honor project, client, manager, and department filters where the fact supports them. `Period` measures honor the date slicer. The exact DAX is in `powerbi/dax/measures.dax`; this table maps each business definition to its measure, formula, interpretation, check, and example. A positive budget variance means underspend (favorable); a positive forecast overrun means risk (unfavorable).

| # | KPI / DAX measure | Business formula and interpretation | Validation method | Example |
|---:|---|---|---|---|
| 1 | Approved Project Budget Lifetime | Sum department allocations in the latest approved version per project. Authorized lifetime ceiling. | Sum selected `FactBudget` versions by project; compare `ProjectMetrics`. | Portfolio $36,417,000.00. |
| 2 | Actual Project Cost Lifetime | Net posted cost, including negative corrections, through as-of. | Sum `FactActualCost.amount`; reconcile to project extract. | Portfolio $31,128,158.99. |
| 3 | Budget Variance Lifetime | Budget − actual; negative means overspend. | Recompute from KPIs 1–2. | P001 −$181,837.47. |
| 4 | Budget Variance % Lifetime | (Budget − actual) ÷ budget. | Divide #3 by #1 for nonzero budgets. | P001 −37.88%. |
| 5 | Budget Utilization % Lifetime | Actual ÷ budget; >100% means over budget. | Divide #2 by #1. | Portfolio 85.48%. |
| 6 | Recognized Revenue Lifetime | Sum recognized revenue postings; independent of cash/invoices. | Sum `FactRevenue.recognized_revenue_usd`. | Portfolio $40,638,135.28. |
| 7 | Gross Project Profit Lifetime | Recognized revenue − eligible project cost. | Recompute #6 − #2. | Portfolio $9,509,976.29. |
| 8 | Gross Profit Margin % Lifetime | Gross profit ÷ recognized revenue; weighted portfolio margin. | Divide #7 by #6. | Portfolio 23.40%. |
| 9 | Total Forecast Cost Base | Sum future monthly cost in latest base snapshot; future spend only. | Sum filtered `FactForecast.forecast_cost_usd`. | Portfolio $8,610,989.86. |
| 10 | Estimate to Complete Base | Same future-cost sum as #9; cost still required. | Compare against #9 by project. | P003 $97,260.51. |
| 11 | Estimate at Completion Base | Lifetime actual + estimate to complete. | Recompute #2 + #10. | P003 $843,936.83. |
| 12 | Forecast Cost Overrun Base | Sum per-project `max(0, EAC − approved budget)`; positive is unfavorable. | Recompute rowwise, then sum. | P003 $43,936.83; portfolio $4,045,824.52. |
| 13 | Project Financial Health | Over budget, else at risk by EAC, else low margin under 15%, else on track. | Compare against ordered rules in `project_metrics`. | P003 `At risk`. |
| 14 | Monthly Cost Growth % | (Current month cost − prior month cost) ÷ prior month cost. | Compare monthly grouped actuals. | Sep 2026 −5.36% vs Aug. |
| 15 | Year-over-Year Revenue Growth % | (Current period revenue − same period prior year) ÷ prior-year revenue. | Compare monthly grouped revenue with prior year. | Sep 2026 −12.91%. |
| 16 | Average Project Margin % | Arithmetic mean of project lifetime margins; distinct from weighted #8. | Average `ProjectMetrics.gross_margin_pct` over projects with revenue. | Portfolio 22.27%. |
| 17 | Cost by Department | Period net actual cost under department filter. | Group `FactActualCost` by department ID. | D02 $8,635,812.41 lifetime. |
| 18 | Cost by Category | Period net actual cost under category filter. | Group `FactActualCost` by category ID. | Employees $16,064,581.66 lifetime. |
| 19 | Project Completion % | Delivery progress supplied by the synthetic project source; no financial proxy. | Compare `DimProject.completion_pct` with source. | P003 87.38%. |
| 20 | At-Risk Project Count | Count projects with actual < budget but EAC > budget. | Apply rowwise predicate to `ProjectMetrics`. | 19 projects. |
| 21 | Over-Budget Project Count | Count projects with actual > budget. | Apply rowwise predicate to `ProjectMetrics`. | 18 projects. |
| 22 | Actual Cost Period | Sum net cost in selected calendar period. | Filter actual fact by `DimDate`. | Sep 2026 $1,212,277.48. |
| 23 | Recognized Revenue Period | Sum recognized revenue in selected calendar period. | Filter revenue fact by `DimDate`. | Sep 2026 $1,468,951.61. |
| 24 | Gross Project Profit Period | Period recognized revenue − period cost. | Subtract #22 from #23. | Sep 2026 $256,674.13. |
| 25 | Gross Profit Margin % Period | Period gross profit ÷ period recognized revenue. | Divide #24 by #23. | Sep 2026 17.47%. |
| 26 | Remaining Approved Budget | Selected approved lifetime budget − lifetime actual cost; may be negative. | Recompute #1 − #2. | P003 $53,323.68. |
| 27 | Approved Budget As of Date | For each project, sum latest approved version by displayed date. | Compare version sequence and approval dates, especially P004. | Portfolio as of Sep 2026 $36,417,000.00. |

Rates return blank when the denominator is zero. Project financial health returns blank outside a single-project context. Per-project forecast overrun must be summed **after** applying `max(0, …)`; applying one maximum to portfolio totals would let underspends cancel project risks. The completion percentage comes from project delivery metadata and should not be inferred from budget utilization.

