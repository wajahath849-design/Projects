// Create Power BI text parameters ServerName and DatabaseName first.
// Default values: localhost,1433 and AppleFinancialReporting.

let
    Source = Sql.Database(ServerName, DatabaseName),
    FinancialSummary = Source{[Schema="reporting", Item="vw_FinancialSummary"]}[Data]
in
    FinancialSummary

// Repeat the navigation step for:
// reporting.vw_FinancialFacts
// reporting.vw_ETLRunHistory
// reporting.vw_DataQualityIssues
