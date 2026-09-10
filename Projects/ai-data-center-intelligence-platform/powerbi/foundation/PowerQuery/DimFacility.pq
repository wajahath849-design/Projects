let
    Source = Csv.Document(File.Contents(DataRoot & "\\facilities.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"facility_id", type text}, {"facility_name", type text}, {"city", type text},
        {"country", type text}, {"region", type text}, {"capacity_mw", type number},
        {"rack_capacity", Int64.Type}, {"build_year", Int64.Type}, {"commission_date", type date}
    })
in
    Typed
