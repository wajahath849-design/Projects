let
    Source = Csv.Document(File.Contents(DataRoot & "\\maintenance_actions.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"action_id", type text}, {"incident_id", type text}, {"facility_id", type text},
        {"server_id", type text}, {"timestamp", type datetime}, {"action_type", type text},
        {"description", type text}, {"result", type text}, {"performed_by_role", type text}
    }),
    ActionDate = Table.AddColumn(Typed, "action_date", each Date.From([timestamp]), type date)
in
    ActionDate
