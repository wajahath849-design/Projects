SELECT * FROM {{ source('operational', 'operational_incidents') }}
