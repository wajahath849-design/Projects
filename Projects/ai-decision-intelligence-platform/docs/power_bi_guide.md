# Power BI guide

The repository supplies a manual construction package, not a generated `.pbix` file.

1. Run `scripts/export_power_bi_data.py` to create/refresh reporting views and sample exports.
2. Import `powerbi/theme/decision_intelligence_theme.json` in Power BI Desktop.
3. Follow `powerbi/docs/data_model.md` for Power Query and relationships.
4. Create a `_Measures` table and paste measures from `powerbi/dax/measures.dax`.
5. Build the seven pages using `powerbi/docs/page_layouts.md`.
6. Apply `powerbi/docs/formatting_and_interactions.md`.
7. Complete `powerbi/tests/power_bi_checklist.md` before sharing.

The `powerbi/exports` folder contains source-backed CSVs and `manifest.json`, allowing report
construction to be verified even on a machine without Power BI Desktop.
