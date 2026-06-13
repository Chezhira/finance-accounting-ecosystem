import os
import unittest
from unittest.mock import patch

os.environ["RBAC_ENABLED"] = "false"

from fastapi.testclient import TestClient

from api import main
from ingestion import ingestor


class OCRIngestionTests(unittest.TestCase):
    def test_text_layer_pdf_keeps_native_path(self):
        native_text = "A" * ingestor.PDF_NATIVE_TEXT_MIN_CHARS
        with patch.object(ingestor, "_extract_pdf_text", return_value=native_text), patch.object(
            ingestor, "_ocr_pdf"
        ) as ocr_pdf:
            result = ingestor.DataIngestor.from_file(b"pdf", "invoice.pdf")
        self.assertFalse(result["ocr_used"])
        self.assertEqual(result["source_type"], "file_pdf")
        ocr_pdf.assert_not_called()

    def test_scanned_pdf_triggers_ocr_fallback(self):
        with patch.object(ingestor, "_extract_pdf_text", return_value=""), patch.object(
            ingestor, "_ocr_pdf", return_value=("Readable scanned invoice total 5000", 2, 91.0)
        ):
            result = ingestor.DataIngestor.from_file(b"pdf", "scan.pdf")
        self.assertTrue(result["ocr_used"])
        self.assertEqual(result["ocr_page_count"], 2)

    def test_image_upload_triggers_ocr(self):
        with patch.object(
            ingestor, "_ocr_image", return_value=("Readable photographed receipt total 25", 88.0)
        ):
            result = ingestor.DataIngestor.from_file(b"image", "receipt.jpg")
        self.assertTrue(result["ocr_used"])
        self.assertEqual(result["source_type"], "file_image_ocr")

    def test_low_quality_ocr_is_rejected(self):
        with patch.object(ingestor, "_extract_pdf_text", return_value=""), patch.object(
            ingestor, "_ocr_pdf", return_value=("too short", 1, 10.0)
        ):
            with self.assertRaises(ingestor.OCRProcessingError):
                ingestor.DataIngestor.from_file(b"pdf", "scan.pdf")

    def test_missing_dependency_is_configuration_error(self):
        with patch.object(ingestor, "OCR_AVAILABLE", False):
            with self.assertRaises(ingestor.OCRConfigurationError):
                ingestor._ocr_pdf(b"pdf")

    def test_pdf_page_limit_is_enforced_before_conversion(self):
        with patch.object(ingestor, "OCR_AVAILABLE", True), patch.object(
            ingestor, "pdfinfo_from_bytes", return_value={"Pages": ingestor.OCR_MAX_PAGES + 1}
        ), patch.object(ingestor, "convert_from_bytes") as convert:
            with self.assertRaises(ingestor.OCRPageLimitError):
                ingestor._ocr_pdf(b"pdf")
        convert.assert_not_called()

    def test_api_propagates_upload_ocr_source(self):
        client = TestClient(main.app)
        result = {
            "text": "Readable scanned invoice total 5000",
            "ocr_used": True,
            "warnings": [],
        }
        with patch.object(main.ingestor, "from_file", return_value=result), patch.object(
            main, "_run_ingest_and_process", return_value=("id-1", {"ok": True})
        ) as process:
            response = client.post(
                "/ingest/upload",
                params={"tenant_id": "chezsolutions_tz", "jurisdiction": "TZ"},
                files={"file": ("scan.png", b"image", "image/png")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(process.call_args.args[3], "upload_ocr")

    def test_api_returns_clean_dependency_error(self):
        client = TestClient(main.app)
        with patch.object(main.ingestor, "from_file", side_effect=ingestor.OCRConfigurationError()):
            response = client.post(
                "/ingest/upload",
                files={"file": ("scan.png", b"image", "image/png")},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["source"], "upload_ocr_config_error")


if __name__ == "__main__":
    unittest.main()
