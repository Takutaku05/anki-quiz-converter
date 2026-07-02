import logging
import unittest

from fastapi.testclient import TestClient

from src.api import LOGGER, create_app
from src.download_store import InMemoryDownloadStore
from sample_data import SAMPLE_SOURCE


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
