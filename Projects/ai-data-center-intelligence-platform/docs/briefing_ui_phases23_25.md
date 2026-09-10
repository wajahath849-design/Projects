# Phases 23–25: Operations Briefing and Copilot UI

## Monthly operations briefing

`OperationsBriefingEngine` calculates a selected month and its previous month directly from SQLite. It reports:

- the largest month-over-month PUE change;
- incident count, critical incident count, and downtime;
- the facility with highest network availability;
- the largest CPU-utilization change;
- high and critical anomaly count;
- the highest five-year PUE projection;
- the top three governed investigation priorities.

Every statement has structured source evidence. Forecast text is explicitly labelled as a projection, and recommended investigations come from the fixed decision-support model.

## Streamlit layout

The app is organized into three tabs:

- **Chat** for conversational analytics and investigations;
- **Operations brief** for proactive monthly summaries;
- **Health & risk** for governed facility and server scores.

The sidebar contains dataset status, facility/date filters, optional analysis-mode override, recent questions, new-conversation control, and Ollama status. Starting a new conversation clears both visible messages and structured operational context.

Assistant results persist in session state with their table, chart, evidence, execution path, and timings. The main answer remains readable; detailed provenance and diagnostics are collapsed by default.

## Incident investigation card

Incident results display:

- incident, facility, severity, affected server, and deterministic confidence;
- likely area to inspect;
- source-labelled timeline with timestamp precision;
- reviewed operator checks and authorization warning;
- expandable metrics, logs, alerts, anomalies, runbooks, history, and confidence breakdown.

The UI does not present recommendations as approved actions.

## Streamlit skill status

The Streamlit implementation was checked against the installed version-matched guidance and uses native cached resources, tabs, columns, chat, dataframes, Plotly, expanders, and session state. A live browser run validated chat, monthly briefing, facility health, server risk, duplicated scenarios, and the direct-action warning without browser errors.

## Performance behavior

- The initialized analytics pipeline is cached as a resource.
- Conversation memory stores eight fields rather than full prompt history.
- Advanced operational modes are deterministic and use zero LLM calls.
- Evidence and technical detail render only when expanded.
- Briefing and score calculations run on user action, not every page rerun.
