let
    Source = Csv.Document(File.Contents(DataRoot & "\\powerbi_live_operations_snapshot.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"simulation_session_id", type text}, {"scenario_name", type text},
        {"session_status", type text}, {"snapshot_timestamp", type datetime},
        {"facility_id", type text}, {"facility_name", type text}, {"health_score", type number},
        {"energy_efficiency_score", type number}, {"reliability_score", type number},
        {"network_health_score", type number}, {"infrastructure_score", type number},
        {"alert_score", type number}, {"anomaly_score", type number},
        {"active_alert_count", Int64.Type}, {"active_anomaly_count", Int64.Type},
        {"data_completeness_pct", type number}, {"method_version", type text},
        {"is_synthetic", type logical}, {"snapshot_version", type text}
    })
in
    Typed
