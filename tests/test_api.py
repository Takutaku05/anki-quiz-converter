import io
import logging
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from src.api import LOGGER, create_app
from src.download_store import InMemoryDownloadStore
from sample_data import SAMPLE_SOURCE

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_PDF = os.path.join(FIXTURE_DIR, "sample_quiz_ja.pdf")


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _encrypted_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryDownloadStore(expires_in_seconds=1800)
        self.client = TestClient(create_app(store=self.store))

    def test_convert_returns_tsv(self):
        response = self.client.post(
            "/api/convert",
            json={"source": SAMPLE_SOURCE, "create_download_link": False},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deck"], "薬理学Ⅲ::テスト単元")
        self.assertGreater(data["card_count"], 0)
        self.assertTrue(data["tsv"].startswith("#separator:Tab"))
        self.assertIsNone(data["downloads"]["apkg"])
        self.assertEqual(data["warnings"], [])

    def test_capabilities_reports_links_enabled(self):
        response = self.client.get("/api/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"apkg_download_links_enabled": True, "link_ttl_seconds": 1800},
        )

    def test_convert_creates_download_link_and_serves_apkg(self):
        response = self.client.post(
            "/api/convert",
            json={"source": SAMPLE_SOURCE, "create_download_link": True},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        apkg = data["downloads"]["apkg"]
        self.assertIsNotNone(apkg)
        self.assertEqual(apkg["filename"], "薬理学Ⅲ_テスト単元.apkg")
        self.assertEqual(apkg["expires_in_seconds"], 1800)
        self.assertIn("/api/download/", apkg["url"])
        self.assertIsNone(data["downloads"]["tsv"])

        download = self.client.get(apkg["url"])
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.content.startswith(b"PK"))
        self.assertIn("attachment", download.headers["content-disposition"])
        self.assertEqual(download.headers["cache-control"], "no-store")

    def test_download_with_unknown_token_returns_404(self):
        response = self.client.get("/api/download/unknown-token")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "リンクが無効か、有効期限が切れています。もう一度変換してください。",
        )

    def test_convert_returns_japanese_error(self):
        response = self.client.post(
            "/api/convert",
            json={"source": "問1\n1. テスト（○）", "create_download_link": False},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "タイトルからデッキ名を抽出できません。")

    def test_extract_pdf_returns_text(self):
        with open(SAMPLE_PDF, "rb") as handle:
            response = self.client.post(
                "/api/extract-pdf",
                files={"file": ("quiz.pdf", handle.read(), "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("レボセチリジン", data["text"])
        self.assertGreaterEqual(data["page_count"], 1)
        self.assertEqual(data["char_count"], len(data["text"]))

    def test_extract_pdf_rejects_non_pdf(self):
        response = self.client.post(
            "/api/extract-pdf",
            files={"file": ("notes.txt", b"hello world", "text/plain")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "PDFファイルを選択してください。")

    def test_extract_pdf_rejects_oversized_file(self):
        payload = b"%PDF-" + b"0" * (10 * 1024 * 1024 + 1)
        response = self.client.post(
            "/api/extract-pdf",
            files={"file": ("big.pdf", payload, "application/pdf")},
        )

        self.assertEqual(response.status_code, 413)
        self.assertIn("大きすぎます", response.json()["detail"])

    def test_extract_pdf_rejects_encrypted(self):
        response = self.client.post(
            "/api/extract-pdf",
            files={"file": ("locked.pdf", _encrypted_pdf_bytes(), "application/pdf")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("暗号化", response.json()["detail"])

    def test_extract_pdf_scanned_returns_error(self):
        response = self.client.post(
            "/api/extract-pdf",
            files={"file": ("scan.pdf", _blank_pdf_bytes(), "application/pdf")},
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("画像として保存されたPDF", response.json()["detail"])

    def test_unhandled_errors_are_logged(self):
        app = create_app(store=self.store)

        @app.get("/api/boom")
        def boom():
            raise RuntimeError("boom")

        client = TestClient(app)

        with self.assertLogs("anki_quiz_converter.api", level="ERROR") as logs:
            with self.assertRaises(RuntimeError):
                client.get("/api/boom")

        output = "\n".join(logs.output)
        self.assertIn("Unhandled API error method=GET path=/api/boom", output)
        self.assertIn("RuntimeError: boom", output)

    def test_http_exceptions_are_not_logged_as_unhandled(self):
        with self.assertNoLogs("anki_quiz_converter.api", level="ERROR"):
            response = self.client.get("/api/download/unknown-token")

        self.assertEqual(response.status_code, 404)

    def test_invalid_log_level_falls_back_to_info(self):
        original_level = LOGGER.level
        self.addCleanup(LOGGER.setLevel, original_level)

        with mock.patch.dict(os.environ, {"LOG_LEVEL": "not-a-level"}):
            create_app(store=self.store)

        self.assertEqual(LOGGER.level, logging.INFO)

    def test_log_level_is_reapplied_when_handler_already_configured(self):
        original_level = LOGGER.level
        self.addCleanup(LOGGER.setLevel, original_level)
        self.assertTrue(LOGGER.handlers, "expected a handler from an earlier create_app() call")

        with mock.patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            create_app(store=self.store)

        self.assertEqual(LOGGER.level, logging.DEBUG)

    def test_error_logger_format_includes_timestamp(self):
        formatter = LOGGER.handlers[0].formatter
        record = logging.LogRecord(
            name=LOGGER.name,
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="sample error",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        self.assertRegex(formatted, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        self.assertIn("ERROR anki_quiz_converter.api sample error", formatted)


if __name__ == "__main__":
    unittest.main()
