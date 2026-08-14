let
    Source = Csv.Document(File.Contents(DataRoot & "\\network_metrics.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"metric_id", type text}, {"facility_id", type text}, {"timestamp", type date},
        {"bandwidth_utilization_pct", type number}, {"latency_ms", type number},
        {"packet_loss_pct", type number}, {"throughput_mbps", type number},
        {"network_availability_pct", type number}
    })
in
    Typed

