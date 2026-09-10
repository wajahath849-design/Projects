let
    Source = Csv.Document(File.Contents(DataRoot & "\\facility_health_scores.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"health_score_id", type text}, {"score_date", type date}, {"source_year", Int64.Type},
        {"facility_id", type text}, {"health_score", type number},
        {"energy_efficiency_score", type number}, {"reliability_score", type number},
        {"network_health_score", type number}, {"infrastructure_utilization_score", type number},
        {"incident_severity_score", type number}, {"anomaly_frequency_score", type number},
        {"weights_version", type text}, {"weights_json", type text}
    })
in
    Typed
