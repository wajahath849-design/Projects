SELECT DISTINCT channel FROM {{ ref('stg_web_sessions') }}
