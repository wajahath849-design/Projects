let
    Source = Csv.Document(File.Contents(DataRoot & "\\server_metrics.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"metric_id", type text}, {"server_id", type text}, {"timestamp", type date},
        {"cpu_utilization_pct", type number}, {"memory_utilization_pct", type number},
        {"disk_utilization_pct", type number}, {"network_utilization_pct", type number}
    })
in
    Typed
