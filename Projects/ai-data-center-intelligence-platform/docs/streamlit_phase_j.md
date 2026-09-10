# Phase J — Streamlit Operations Workbench

The app now uses modern `st.navigation` with six focused pages: Operations
copilot, Live ops, Simulation lab, Investigation, Cost & sustainability, and
Impact analysis. Shared resources are bounded with `st.cache_resource`, while
per-user controls and active simulation context remain in session state.

Live ops refreshes independently every five seconds. Simulation controls expose
start, advance, run-to-end, pause, resume, reset, replay, and four speeds. The
investigation page shows analyst counts, findings, evidence, confidence, and
operator checks—but no private reasoning. Cost/carbon and impact pages use
native KPI cards, charts, forms, tables, and explicit caveats. A native light/
dark theme is configured without fragile custom CSS.
