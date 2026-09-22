import pandas as pd
from django.test import SimpleTestCase

from apps.audits.engine import AuditInputError, AuditSpec
from apps.audits.scope import analyze_scoped


class ScopedAnalysisTests(SimpleTestCase):
    def setUp(self):
        self.frame = pd.DataFrame([
            {"date": "2026-01-01", "wins": 1, "trials": 10, "region": "Berlin", "category": "A"},
            {"date": "2026-01-08", "wins": 2, "trials": 10, "region": "Berlin", "category": "B"},
            {"date": "2026-02-01", "wins": 3, "trials": 10, "region": "Berlin", "category": "A"},
            {"date": "2026-02-08", "wins": 4, "trials": 10, "region": "Berlin", "category": "B"},
            {"date": "2026-01-01", "wins": 1, "trials": 10, "region": "Paris", "category": "A"},
            {"date": "2026-01-08", "wins": 1, "trials": 10, "region": "Paris", "category": "B"},
            {"date": "2026-02-01", "wins": 1, "trials": 10, "region": "Paris", "category": "A"},
            {"date": "2026-02-08", "wins": 1, "trials": 10, "region": "Paris", "category": "B"},
        ])
        self.spec = AuditSpec("Win rate", "Win rate improved", "wins", "trials", "date", ["region", "category"], "2026-02-01")

    def test_combines_dimensions_and_discloses_filter_scope(self):
        result = analyze_scoped(self.frame, self.spec, {"region": ["Berlin"]})
        self.assertEqual(result["contract"]["segment_columns"], ["region", "category"])
        self.assertEqual(result["contract"]["filters"], {"region": ["Berlin"]})
        self.assertEqual(result["contract"]["source_rows"], 8)
        self.assertEqual(result["contract"]["filtered_rows"], 4)
        self.assertEqual({row["segment"] for row in result["segments"]}, {'region="Berlin" · category="A"', 'region="Berlin" · category="B"'})

    def test_rejects_empty_and_invalid_filters(self):
        for filters in ({"region": []}, {"unknown": ["x"]}, {"region": "Berlin"}):
            with self.subTest(filters=filters), self.assertRaises(AuditInputError):
                analyze_scoped(self.frame, self.spec, filters)

    def test_rejects_duplicate_group_columns(self):
        spec = AuditSpec("Win rate", "Claim", "wins", "trials", "date", ["region", "region"])
        with self.assertRaisesMessage(AuditInputError, "unique grouping"):
            analyze_scoped(self.frame, spec, {})
