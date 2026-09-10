let
    Source = Csv.Document(File.Contents(DataRoot & "\\alerts.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"alert_id", type text}, {"timestamp", type datetime}, {"facility_id", type text},
        {"server_id", type text}, {"component", type text}, {"severity", type text},
        {"alert_type", type text}, {"metric_name", type text}, {"observed_value", type number},
        {"threshold_value", type number}, {"status", type text}, {"resolved_at", type datetime}
    }),
    AlertDate = Table.AddColumn(Typed, "alert_date", each Date.From([timestamp]), type date)
in
    AlertDate
