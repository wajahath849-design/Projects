let
    Source = Csv.Document(File.Contents(DataRoot & "\\powerbi_cost_carbon_snapshot.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"snapshot_date", type date}, {"year", Int64.Type}, {"month_label", type text},
        {"facility_id", type text}, {"facility_name", type text}, {"observation_days", Int64.Type},
        {"modeled_energy_kwh", type number}, {"modeled_it_energy_kwh", type number},
        {"modeled_cooling_energy_kwh", type number}, {"modeled_energy_cost_usd", type number},
        {"modeled_it_cost_usd", type number}, {"modeled_cooling_cost_usd", type number},
        {"modeled_carbon_tonnes", type number}, {"modeled_it_carbon_tonnes", type number},
        {"modeled_cooling_carbon_tonnes", type number}, {"average_pue", type number},
        {"price_per_kwh", type number}, {"grams_co2e_per_kwh", type number},
        {"efficiency_opportunity_score", type number}, {"currency", type text},
        {"pricing_basis", type text}, {"price_source", type text},
        {"carbon_methodology", type text}, {"carbon_source", type text},
        {"assumptions_are_synthetic", type logical}, {"snapshot_version", type text},
        {"source_period", type text}
    })
in
    Typed
