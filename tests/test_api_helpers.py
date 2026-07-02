import unittest

from src.api_helpers import (
    build_download_filename,
    count_tsv_cards,
    japanese_error_message,
)


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


if __name__ == "__main__":
    unittest.main()
