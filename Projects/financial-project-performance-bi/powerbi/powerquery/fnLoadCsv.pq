(FileName as text, ColumnTypes as list) as table =>
let
    Source = Csv.Document(
        File.Contents(CuratedFolder & "\" & FileName),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Headers, ColumnTypes, "en-US")
in
    Typed
