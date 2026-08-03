# Power BI validation checklist

- [ ] All seven `vw_PBI_*` views load without SQL errors.
- [ ] Date is marked as the date table and every active relationship is one-to-many.
- [ ] No ambiguous or bidirectional filter path exists.
- [ ] All DAX measures compile and divide-by-zero cases return zero, not errors.
- [ ] Executive totals reconcile to their source SQL views.
- [ ] Forecast bounds contain forecast values and horizon slicers return 7/30/90.
- [ ] Inventory statuses use the configured five labels.
- [ ] Recommendation quantities are integers and SolverStatus is OPTIMAL or FEASIBLE.
- [ ] Every scenario shows preserved baseline values and changed scenario values.
- [ ] Exactly one model is marked production.
- [ ] Latest data-quality run contains no critical failures.
- [ ] Currency, units, dates, percentages, risk colors, and solver colors are consistent.
- [ ] Drill-through back buttons and tooltips work on Pages 2–5.
- [ ] Empty selections show zero/blank intentionally rather than broken visuals.
- [ ] Synthetic data disclosure is visible.
- [ ] No screenshot or PBIX claim is made unless Power BI Desktop was actually used.
