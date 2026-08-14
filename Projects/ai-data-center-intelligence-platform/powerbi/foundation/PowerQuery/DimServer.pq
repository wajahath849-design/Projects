let
    Source = Csv.Document(File.Contents(DataRoot & "\\servers.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"server_id", type text}, {"facility_id", type text}, {"rack_id", type text},
        {"server_type", type text}, {"cpu_cores", Int64.Type}, {"memory_gb", Int64.Type},
        {"install_date", type date}, {"status", type text}
    })
in
    Typed

