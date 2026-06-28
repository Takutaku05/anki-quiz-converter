from datetime import UTC, datetime
import unittest

from src.api_helpers import (
    build_download_filename,
    count_tsv_cards,
    japanese_error_message,
)
from src.r2_storage import R2DownloadStore, R2Settings


class FakeS3Client:
    def __init__(self):
        self.put_kwargs = None

    def put_object(self, **kwargs):
        self.put_kwargs = kwargs

    def generate_presigned_url(self, client_method, Params, ExpiresIn):
        return f"https://download.example/{Params['Key']}?expires={ExpiresIn}&method={client_method}"


class ApiHelperTests(unittest.TestCase):
    def test_japanese_error_message_maps_known_converter_errors(self):
        self.assertEqual(
            japanese_error_message(ValueError("deck name could not be extracted from the title")),
            "タイトルからデッキ名を抽出できません。",
        )
        self.assertEqual(
            japanese_error_message(ValueError("no question blocks were found")),
            "問題ブロックが見つかりません。",
        )
        self.assertEqual(
            japanese_error_message(ValueError("no answer choices were found")),
            "解答選択肢が見つかりません。",
        )

    def test_count_tsv_cards_ignores_anki_headers(self):
        tsv = "\n".join(
            [
                "#separator:Tab",
                "#html:true",
                "#deck:薬理学Ⅲ::アレルギー",
                "表\t裏\tタグ",
                "表2\t裏2\tタグ2",
                "",
            ]
        )

        self.assertEqual(count_tsv_cards(tsv), 2)

    def test_build_download_filename_removes_path_unsafe_characters(self):
        self.assertEqual(
            build_download_filename("薬理学Ⅲ::消化器/潰瘍", "tsv"),
            "薬理学Ⅲ_消化器_潰瘍.tsv",
        )

    def test_r2_download_store_uploads_and_returns_presigned_url(self):
        client = FakeS3Client()
        store = R2DownloadStore(
            settings=R2Settings(
                bucket_name="anki-files",
                public_prefix="generated",
                expires_in_seconds=3600,
            ),
            client=client,
            now=lambda: datetime(2026, 6, 28, 12, 0, tzinfo=UTC),
        )

        link = store.upload_download(
            content=b"statement\tanswer\ttag\n",
            filename="薬理学.tsv",
            content_type="text/tab-separated-values; charset=utf-8",
        )

        self.assertEqual(client.put_kwargs["Bucket"], "anki-files")
        self.assertEqual(client.put_kwargs["Body"], b"statement\tanswer\ttag\n")
        self.assertEqual(
            client.put_kwargs["ContentType"],
            "text/tab-separated-values; charset=utf-8",
        )
        self.assertTrue(
            client.put_kwargs["ContentDisposition"].startswith(
                "attachment; filename*=UTF-8''"
            )
        )
        self.assertTrue(link.url.startswith("https://download.example/generated/"))
        self.assertEqual(link.filename, "薬理学.tsv")
        self.assertEqual(link.expires_in_seconds, 3600)


if __name__ == "__main__":
    unittest.main()
