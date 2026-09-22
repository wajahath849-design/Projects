from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APITestCase


class PublicApiTests(APITestCase):
    def test_health_endpoint(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")

    def test_demo_endpoint_returns_completed_analysis(self):
        response = self.client.get(reverse("demo"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("confidence_score", response.data)
        self.assertIn(
            "segment-reversal", {item["id"] for item in response.data["findings"]}
        )

    def test_upload_includes_source_and_metric_contract(self):
        response = self.client.post(
            reverse("analyze-upload"),
            {
                "file": SimpleUploadedFile(
                    "checkout.csv",
                    b"date,conversions,sessions\n2026-01-01,10,100\n2026-01-02,10,100\n2026-02-01,20,100\n2026-02-02,20,100\n",
                    content_type="text/csv",
                ),
                "split_date": "2026-02-01",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["contract"]["source_name"], "checkout.csv")
        self.assertEqual(response.data["contract"]["column_count"], 3)
        self.assertEqual(response.data["stress_tests"][0]["status"], "not_applicable")

    def test_unreadable_csv_returns_helpful_bad_request(self):
        for data in [
            b"\n",
            b'date,conversions,sessions\n"unterminated',
            b"\xff,invalid\n",
        ]:
            with self.subTest(data=data):
                response = self.client.post(
                    reverse("analyze-upload"),
                    {
                        "file": SimpleUploadedFile(
                            "invalid.csv", data, content_type="text/csv"
                        )
                    },
                    format="multipart",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("CSV", response.data["detail"])

    def test_invalid_split_date_returns_bad_request(self):
        response = self.client.post(
            reverse("analyze-upload"),
            {
                "file": SimpleUploadedFile(
                    "checkout.csv",
                    b"date,conversions,sessions\n2026-01-01,10,100\n2026-01-02,10,100\n2026-02-01,20,100\n2026-02-02,20,100\n",
                ),
                "split_date": "not-a-date",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valid split date", response.data["detail"])
