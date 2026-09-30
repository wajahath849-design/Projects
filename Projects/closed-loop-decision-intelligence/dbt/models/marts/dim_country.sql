SELECT DISTINCT country FROM {{ ref('stg_web_sessions') }}
