SELECT DISTINCT CAST(timestamp AS date) AS date,
EXTRACT(YEAR FROM timestamp) AS year, EXTRACT(MONTH FROM timestamp) AS month,
EXTRACT(ISODOW FROM timestamp) AS weekday FROM {{ ref('stg_web_sessions') }}
