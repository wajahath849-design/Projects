from dataclasses import replace
import json
import numpy as np

from django.test import SimpleTestCase

from apps.audits.demo import build_demo_frame, demo_spec
from apps.audits.engine import AuditInputError, analyze_dataframe


class AuditEngineTests(SimpleTestCase):
    def test_reserved_and_colliding_segment_names_preserve_chart_values(self):
        for labels in [("date", "aggregate"), ("A B", "a_b")]:
            frame = build_demo_frame()
            frame["device"] = frame["device"].map(dict(zip(["Desktop", "Mobile"], labels)))
            result = analyze_dataframe(frame, demo_spec())
            for point in result["time_series"]:
                self.assertIsInstance(point["date"], str)
                for label in labels:
                    self.assertIn("segment:" + label, point)
            json.dumps(result, allow_nan=False)

    def test_invalid_numeric_values_are_excluded_and_flagged(self):
        frame = build_demo_frame()
        frame["conversions"] = frame["conversions"].astype(float)
        frame.loc[0, "conversions"] = np.inf
        frame.loc[1, "conversions"] = -1
        result = analyze_dataframe(frame, demo_spec())
        self.assertEqual(result["quality"]["invalid_values"], 2)
        self.assertEqual(result["quality"]["valid_rows"], len(frame) - 2)
        json.dumps(result, allow_nan=False)

    def test_zero_baseline_has_no_relative_percentage(self):
        frame = build_demo_frame()
        frame.loc[frame["date"] < "2026-03-02", "conversions"] = 0
        result = analyze_dataframe(frame, demo_spec())
        self.assertIsNone(result["headline"]["relative_change"])

    def test_duplicate_column_mapping_is_rejected(self):
        with self.assertRaisesMessage(AuditInputError, "different columns"):
            analyze_dataframe(build_demo_frame(), replace(demo_spec(), numerator="sessions"))

    def test_new_groups_do_not_pass_full_population_adjustment(self):
        frame = build_demo_frame()
        frame.loc[0, "device"] = "New group"
        result = analyze_dataframe(frame, demo_spec())
        self.assertEqual(result["stress_tests"][0]["status"], "not_applicable")

    def test_missing_group_labels_remain_in_chart(self):
        frame = build_demo_frame()
        frame.loc[frame["device"] == "Mobile", "device"] = None
        result = analyze_dataframe(frame, demo_spec())
        self.assertIn("(Missing)", [row["segment"] for row in result["segments"]])
        self.assertIn("segment:(Missing)", result["time_series"][0])

    def setUp(self):
        self.result = analyze_dataframe(build_demo_frame(), demo_spec())

    def test_detects_segment_reversal(self):
        finding_ids = {finding["id"] for finding in self.result["findings"]}
        self.assertIn("segment-reversal", finding_ids)
        self.assertGreater(self.result["headline"]["absolute_change"], 0)
        self.assertLess(self.result["headline"]["adjusted_absolute_change"], 0)

    def test_returns_json_safe_decision_report(self):
        self.assertIsInstance(self.result["confidence_score"], int)
        self.assertGreaterEqual(len(self.result["stress_tests"]), 5)
        self.assertGreaterEqual(len(self.result["time_series"]), 8)
        self.assertFalse(self.result["methodology"]["ai_used_for_calculation"])

    def test_contract_describes_the_actual_analysis(self):
        contract = self.result["contract"]
        self.assertEqual(contract["numerator_column"], "conversions")
        self.assertEqual(contract["primary_segment"], "device")
        self.assertEqual(contract["column_count"], 7)
        self.assertLess(contract["baseline_end"], contract["split_date"])
        self.assertGreaterEqual(contract["current_start"], contract["split_date"])
        self.assertIn(
            "not a calibrated probability",
            self.result["methodology"]["score_interpretation"],
        )
        self.assertTrue(self.result["limitations"])

    def test_missing_segments_are_not_reported_as_passed(self):
        result = analyze_dataframe(
            build_demo_frame(), replace(demo_spec(), segment_columns=[])
        )
        for check in result["stress_tests"][:2]:
            self.assertEqual(check["status"], "not_applicable")
            self.assertEqual(check["challenged"], "Not evaluated")
        self.assertEqual(result["methodology"]["tests_run"], 3)

    def test_nonoverlapping_segments_are_not_reported_as_passed(self):
        frame = build_demo_frame()
        frame.loc[frame["date"] >= "2026-03-02", "device"] = "Tablet"
        result = analyze_dataframe(frame, demo_spec())
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["stress_tests"][0]["status"], "not_applicable")
        self.assertEqual(result["stress_tests"][1]["status"], "not_applicable")

    def test_single_comparable_segment_cannot_pass_composition_checks(self):
        frame = build_demo_frame()
        frame["device"] = "All devices"
        result = analyze_dataframe(frame, demo_spec())
        self.assertEqual(result["stress_tests"][0]["status"], "not_applicable")
        self.assertEqual(result["stress_tests"][1]["status"], "not_applicable")

    def test_nonproportion_reliability_is_not_reported_as_passed(self):
        result = analyze_dataframe(
            build_demo_frame(), replace(demo_spec(), numerator="revenue")
        )
        reliability = next(
            check
            for check in result["stress_tests"]
            if check["name"] == "Sample reliability"
        )
        self.assertEqual(reliability["status"], "not_applicable")
        self.assertIn("integer success and trial counts", reliability["explanation"])

    def test_invalid_split_date_is_a_user_input_error(self):
        for value in ["invalid-date", "NaT", "2026-02-30"]:
            with (
                self.subTest(value=value),
                self.assertRaisesMessage(AuditInputError, "valid split date"),
            ):
                analyze_dataframe(
                    build_demo_frame(), replace(demo_spec(), split_date=value)
                )

    def test_timezone_split_date_is_normalized(self):
        result = analyze_dataframe(
            build_demo_frame(), replace(demo_spec(), split_date="2026-03-02T00:00:00Z")
        )
        self.assertEqual(result["headline"]["split_date"], "2026-03-02")

    def test_quality_findings_are_reflected_in_verdict(self):
        frame = build_demo_frame()
        frame = frame.loc[frame["device"] == "Desktop"]
        frame = frame.loc[frame.index.repeat(2)]
        result = analyze_dataframe(frame, replace(demo_spec(), segment_columns=[]))
        self.assertIn(
            "data-integrity", [finding["id"] for finding in result["findings"]]
        )
        self.assertEqual(result["verdict"]["label"], "Needs review")
        self.assertIn("require review", result["verdict"]["summary"])
