let
    Source = Csv.Document(File.Contents(DataRoot & "\\system_logs.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"log_id", type text}, {"timestamp", type datetime}, {"facility_id", type text},
        {"server_id", type text}, {"rack_id", type text}, {"source", type text},
        {"component", type text}, {"log_level", type text}, {"event_code", type text}, {"message", type text}
    }),
    LogDate = Table.AddColumn(Typed, "log_date", each Date.From([timestamp]), type date)
in
    LogDate
