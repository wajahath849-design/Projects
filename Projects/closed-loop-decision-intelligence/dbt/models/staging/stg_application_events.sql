SELECT * FROM {{ source('operational', 'application_events') }}
