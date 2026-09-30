import unittest
import pandas as pd

from pipeline.ingest import clean_lines


class CleaningRulesTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame([
            ["100", "12345", "item", 2, "2011-01-01", 5.0, 1, "UK"],
            ["100", "12345", "item", 2, "2011-01-01", 5.0, 1, "UK"],
            ["C101", "12345", "item", -1, "2011-01-02", 5.0, 1, "UK"],
            ["102", "12345", "item", 1, "2011-01-03", 7.0, None, "UK"],
            ["103", "POST", "postage", 1, "2011-01-03", 2.0, 1, "UK"],
        ], columns=["InvoiceNo","StockCode","Description","Quantity","InvoiceDate","UnitPrice","CustomerID","Country"])

    def test_duplicate_and_population_reconcile(self):
        lines, audit = clean_lines(self.sample())
        self.assertEqual(audit["exact_duplicate_rows_removed"], 1)
        self.assertEqual(audit["sale_rows"], 2)
        self.assertEqual(audit["return_rows"], 1)
        self.assertEqual(audit["excluded_rows"], 1)
        self.assertAlmostEqual(audit["all_history_gross_sales"], 17.0)
        self.assertAlmostEqual(audit["all_history_returns_value"], 5.0)

    def test_anonymous_sale_is_commercial_but_not_identified(self):
        _, audit = clean_lines(self.sample())
        self.assertEqual(audit["anonymous_sale_rows"], 1)
        self.assertAlmostEqual(audit["all_history_anonymous_gross_sales"], 7.0)
        self.assertAlmostEqual(audit["all_history_identified_gross_sales"], 10.0)


if __name__ == "__main__":
    unittest.main()
