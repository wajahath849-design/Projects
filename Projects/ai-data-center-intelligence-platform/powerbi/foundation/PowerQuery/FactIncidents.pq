let
    Source = Csv.Document(File.Contents(DataRoot & "\\uptime_incidents.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"incident_id", type text}, {"facility_id", type text}, {"server_id", type text},
        {"start_time", type datetime}, {"end_time", type datetime},
        {"downtime_minutes", Int64.Type}, {"severity", type text},
        {"root_cause", type text}, {"status", type text}
    }),
    IncidentDate = Table.AddColumn(Typed, "incident_date", each Date.From([start_time]), type date)
in
    IncidentDate

