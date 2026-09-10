let
    Source = Csv.Document(File.Contents(DataRoot & "\\detected_anomalies.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"anomaly_id", type text}, {"timestamp", type date}, {"facility_id", type text},
        {"metric_name", type text}, {"observed_value", type number}, {"expected_value", type number},
        {"lower_bound", type number}, {"upper_bound", type number}, {"deviation_pct", type number},
        {"direction", type text}, {"severity", type text}, {"anomaly_score", type number},
        {"method", type text}, {"source_table", type text}, {"source_grain", type text},
        {"source_record_count", Int64.Type}
    })
in
    Typed
