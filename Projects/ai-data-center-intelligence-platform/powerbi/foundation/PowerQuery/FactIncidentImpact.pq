let
    Source = Csv.Document(File.Contents(DataRoot & "\\powerbi_incident_impact_snapshot.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"incident_id", type text}, {"incident_date", type date}, {"facility_id", type text},
        {"facility_name", type text}, {"server_id", type text}, {"severity", type text},
        {"root_cause", type text}, {"status", type text}, {"downtime_minutes", Int64.Type},
        {"during_pue", type number}, {"during_latency_ms", type number},
        {"during_packet_loss_pct", type number}, {"during_network_availability_pct", type number},
        {"before_pue", type number}, {"after_pue", type number},
        {"before_latency_ms", type number}, {"after_latency_ms", type number},
        {"before_packet_loss_pct", type number}, {"after_packet_loss_pct", type number},
        {"before_network_availability_pct", type number}, {"after_network_availability_pct", type number},
        {"change_pue_pct", type number}, {"change_latency_ms_pct", type number},
        {"change_packet_loss_pct_pct", type number}, {"change_network_availability_pct_pct", type number},
        {"modeled_downtime_cost_exposure_usd", type number}, {"comparison_window_days", Int64.Type},
        {"claim_level", type text}, {"is_synthetic", type logical}, {"snapshot_version", type text}
    })
in
    Typed
