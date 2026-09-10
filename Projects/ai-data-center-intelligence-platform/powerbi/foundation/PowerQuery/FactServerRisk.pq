let
    Source = Csv.Document(File.Contents(DataRoot & "\\server_failure_risk.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"risk_id", type text}, {"score_date", type date}, {"forecast_horizon_days", Int64.Type},
        {"server_id", type text}, {"facility_id", type text}, {"risk_score", type number},
        {"risk_level", type text}, {"hardware_error_count", Int64.Type}, {"service_impact_count", Int64.Type},
        {"thermal_signal_count", Int64.Type}, {"incident_count_365d", Int64.Type},
        {"incident_severity_points", Int64.Type}, {"maintenance_count_365d", Int64.Type},
        {"avg_cpu_30d", type number}, {"avg_memory_30d", type number}, {"avg_disk_30d", type number},
        {"asset_age_years", type number}, {"primary_signal", type text}, {"recommendation", type text},
        {"signal_summary_json", type text}, {"lookback_days", Int64.Type}, {"method_version", type text}
    })
in
    Typed
