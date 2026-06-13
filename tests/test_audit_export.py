import csv
import io
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ["RBAC_ENABLED"] = "false"

from fastapi.testclient import TestClient

from api import main
from db.store import OfflineStore


class AuditExportTests(unittest.TestCase):
    def setUp(self):
        # Windows can hold SQLite handles briefly after TestClient threads exit.
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = str(Path(self.temp_dir.name) / "audit.db")
        self.store = OfflineStore(self.db_path)
        self.original_store = main.store
        main.store = self.store
        self.client_manager = TestClient(main.app)
        self.client = self.client_manager.__enter__()

        suggestion = {
            "agent": "TaxSpecialistTZ",
            "document_analysis": {"source": "email"},
            "classification": {"department": "tax"},
            "journal_entry": {"description": "WHT review"},
            "next_action": "Withhold 15%",
        }
        suggestion_id = self.store.save_suggestion(suggestion, "chezsolutions_tz", "TZ")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE suggestions
                   SET status='APPROVED', human_decision='APPROVED',
                       human_notes='Confirmed', decided_by='operator',
                       created_at='2026-06-01T08:00:00+00:00',
                       decided_at='2026-06-01T09:00:00+00:00'
                   WHERE id=?""",
                (suggestion_id,),
            )

    def tearDown(self):
        self.client_manager.__exit__(None, None, None)
        main.store = self.original_store
        self.temp_dir.cleanup()

    def _url(self, **overrides):
        params = {
            "tenant_id": "chezsolutions_tz",
            "from_date": "2026-06-01",
            "to_date": "2026-06-13",
        }
        params.update(overrides)
        return "/audit/export", params

    def test_json_export_success_and_default_format(self):
        url, params = self._url()
        response = self.client.get(url, params=params)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total_records"], 1)
        self.assertEqual(payload["records"][0]["status"], "approved")
        self.assertEqual(payload["records"][0]["source"], "email")
        self.assertEqual(payload["records"][0]["recommendation"], "Withhold 15%")
        self.assertEqual(payload["records"][0]["decision_reason"], "Confirmed")

    def test_csv_export_success_and_headers(self):
        url, params = self._url(format="csv")
        response = self.client.get(url, params=params)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("audit_export_chezsolutions_tz_2026-06-01_2026-06-13.csv", response.headers["content-disposition"])
        rows = list(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(list(rows[0]), main.AUDIT_EXPORT_COLUMNS)
        self.assertEqual(rows[0]["status"], "approved")

    def test_status_filter_and_empty_result(self):
        approved_url, approved_params = self._url(status="approved")
        rejected_url, rejected_params = self._url(status="rejected")
        approved = self.client.get(approved_url, params=approved_params)
        rejected = self.client.get(rejected_url, params=rejected_params)
        self.assertEqual(approved.json()["total_records"], 1)
        self.assertEqual(rejected.json()["total_records"], 0)
        self.assertEqual(rejected.json()["records"], [])

    def test_invalid_inputs_return_400(self):
        cases = [
            {"from_date": "06-01-2026"},
            {"from_date": "2026-06-14", "to_date": "2026-06-13"},
            {"format": "xml"},
            {"status": "posted"},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                url, params = self._url(**overrides)
                response = self.client.get(url, params=params)
                self.assertEqual(response.status_code, 400)

    def test_missing_required_parameter_uses_fastapi_422(self):
        response = self.client.get(
            "/audit/export",
            params={"tenant_id": "chezsolutions_tz", "from_date": "2026-06-01"},
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_tenant_returns_404(self):
        url, params = self._url(tenant_id="missing")
        response = self.client.get(url, params=params)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
