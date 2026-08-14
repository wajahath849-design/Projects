let
    Source = Csv.Document(File.Contents(DataRoot & "\\power_metrics.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"metric_id", type text}, {"facility_id", type text}, {"timestamp", type date},
        {"power_draw_kw", type number}, {"it_load_kw", type number},
        {"cooling_power_kw", type number}, {"pue", type number}, {"cooling_cost", type number}
    })
in
    Typed

