import os
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import src.api as api_module
from src.api import create_app
from src.r2_storage import DownloadLink


ROOT = Path(__file__).resolve().parents[1]
R2_ENV_KEYS = [
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_NAME",
]


class ApiTests(unittest.TestCase):
    def tearDown(self):
        api_module.R2DownloadStore.from_env = self.original_from_env
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        self.original_env = {key: os.environ.get(key) for key in R2_ENV_KEYS}
        self.original_from_env = api_module.R2DownloadStore.from_env
        for key in R2_ENV_KEYS:
            os.environ.pop(key, None)
        self.client = TestClient(create_app())

    def test_convert_returns_tsv_without_r2_settings(self):
        source = (ROOT / "example" / "sauce" / "アレルギー疾患治療薬.txt").read_text(
            encoding="utf-8"
        )

        response = self.client.post(
            "/api/convert",
            json={"source": source, "create_download_link": True},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["deck"], "薬理学Ⅲ::アレルギー疾患治療薬")
        self.assertGreater(data["card_count"], 0)
        self.assertTrue(data["tsv"].startswith("#separator:Tab"))
        self.assertIsNone(data["downloads"]["apkg"])
        self.assertEqual(
            data["warnings"],
            ["R2設定が未設定のため、期限付きダウンロードリンクは作成されませんでした。"],
        )

    def test_capabilities_reports_r2_disabled_without_settings(self):
        response = self.client.get("/api/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"apkg_download_links_enabled": False, "link_ttl_seconds": None},
        )

    def test_capabilities_reports_r2_enabled_with_settings(self):
        os.environ["R2_ACCOUNT_ID"] = "account"
        os.environ["R2_ACCESS_KEY_ID"] = "access"
        os.environ["R2_SECRET_ACCESS_KEY"] = "secret"
        os.environ["R2_BUCKET_NAME"] = "bucket"
        os.environ["R2_LINK_TTL_SECONDS"] = "7200"

        response = self.client.get("/api/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"apkg_download_links_enabled": True, "link_ttl_seconds": 7200},
        )

    def test_convert_uploads_apkg_when_download_link_is_requested(self):
        class FakeStore:
            def __init__(self):
                self.upload = None

            def upload_download(self, content, filename, content_type):
                self.upload = {
                    "content": content,
                    "filename": filename,
                    "content_type": content_type,
                }
                return DownloadLink(
                    url="https://download.example/generated/test.apkg",
                    filename=filename,
                    expires_at="2026-06-29T12:00:00+00:00",
                    expires_in_seconds=86400,
                )

        fake_store = FakeStore()
        api_module.R2DownloadStore.from_env = classmethod(lambda cls: fake_store)
        source = (ROOT / "example" / "sauce" / "アレルギー疾患治療薬.txt").read_text(
            encoding="utf-8"
        )

        response = self.client.post(
            "/api/convert",
            json={"source": source, "create_download_link": True},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["downloads"]["apkg"]["filename"], "薬理学Ⅲ_アレルギー疾患治療薬.apkg")
        self.assertIsNone(data["downloads"]["tsv"])
        self.assertEqual(fake_store.upload["filename"], "薬理学Ⅲ_アレルギー疾患治療薬.apkg")
        self.assertEqual(fake_store.upload["content_type"], "application/octet-stream")
        self.assertTrue(fake_store.upload["content"].startswith(b"PK"))

    def test_convert_returns_japanese_error(self):
        response = self.client.post(
            "/api/convert",
            json={"source": "問1\n1. テスト（○）", "create_download_link": False},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "タイトルからデッキ名を抽出できません。")


if __name__ == "__main__":
    unittest.main()
