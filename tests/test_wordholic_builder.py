import csv
import io
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from src.api import create_app
from src.api_helpers import build_wordholic_filename
from src.download_store import InMemoryDownloadStore
from src.wordholic_builder import (
    WORDHOLIC_HEADER,
    build_wordholic_csv,
    parse_tsv_cards,
)
from sample_data import SAMPLE_SOURCE


def _rows(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


class WordHolicHeaderTests(unittest.TestCase):
    def test_header_matches_wordholic_sample(self):
        csv_text = build_wordholic_csv("表\t裏\tタグ\n")

        self.assertEqual(_rows(csv_text)[0], WORDHOLIC_HEADER)
        self.assertEqual(
            WORDHOLIC_HEADER,
            ["FrontText", "BackText", "Comment", "FrontTextLanguage", "BackTextLanguage"],
        )


class WordHolicCardMappingTests(unittest.TestCase):
    def test_statement_answer_tag_map_to_front_back_comment(self):
        tsv = "\n".join(
            [
                "レボセチリジンは、くしゃみを抑制する。\t○\t問1",
                "クロモグリク酸は、CysLT1受容体を遮断する。\t×\t問2",
                "",
            ]
        )

        rows = _rows(build_wordholic_csv(tsv))

        self.assertEqual(
            rows[1][:3],
            ["レボセチリジンは、くしゃみを抑制する。", "○", "問1"],
        )
        self.assertEqual(
            rows[2][:3],
            ["クロモグリク酸は、CysLT1受容体を遮断する。", "×", "問2"],
        )

    def test_missing_tag_produces_empty_comment(self):
        rows = _rows(build_wordholic_csv("表\t裏\n"))

        self.assertEqual(rows[1][:3], ["表", "裏", ""])

    def test_language_columns_are_always_ja_jp(self):
        tsv = "\n".join(["表1\t裏1\tタグ1", "表2\t裏2\tタグ2", ""])

        for row in _rows(build_wordholic_csv(tsv))[1:]:
            self.assertEqual(row[3], "ja-JP")
            self.assertEqual(row[4], "ja-JP")

    def test_anki_header_and_blank_lines_are_skipped(self):
        tsv = "\n".join(
            [
                "#separator:Tab",
                "#html:true",
                "#deck:薬理学Ⅲ::テスト単元",
                "表\t裏\tタグ",
                "",
            ]
        )

        rows = _rows(build_wordholic_csv(tsv))

        # header + a single card row only
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][:3], ["表", "裏", "タグ"])


class WordHolicLineBreakTests(unittest.TestCase):
    def test_single_and_double_br_convert_to_newlines(self):
        tsv = "前半<br>後半\t上<br><br>下\tメモ<BR>続き\n"

        card = parse_tsv_cards(tsv)[0]

        self.assertEqual(card.front, "前半\n後半")
        self.assertEqual(card.back, "上\n\n下")
        self.assertEqual(card.comment, "メモ\n続き")

    def test_br_variants_with_whitespace_and_slash(self):
        card = parse_tsv_cards("a<br />b<br/>c\t裏\n")[0]

        self.assertEqual(card.front, "a\nb\nc")


class WordHolicRawTabParsingTests(unittest.TestCase):
    def test_double_quotes_are_treated_as_literals(self):
        # Anki TSV is raw tab-separated (not CSV-quoted), so a " directly before
        # a tab must not swallow the tab delimiter.
        card = parse_tsv_cards('A "B\tC" D\t○\t問1\n')[0]

        self.assertEqual(card.front, 'A "B')
        self.assertEqual(card.back, 'C" D')
        self.assertEqual(card.comment, "○")

    def test_field_containing_quotes_is_preserved(self):
        card = parse_tsv_cards('アドレナリンは"昇圧薬"である。\t○\t問1\n')[0]

        self.assertEqual(card.front, 'アドレナリンは"昇圧薬"である。')


class WordHolicQuotingTests(unittest.TestCase):
    def test_fields_with_commas_and_newlines_are_quoted(self):
        tsv = "A, B, C<br>次の行\t答え, その他\tタグ\n"

        csv_text = build_wordholic_csv(tsv)

        # Raw output keeps the field quoted so commas/newlines stay inside one cell.
        self.assertIn('"A, B, C\n次の行"', csv_text)
        # And it round-trips back to the exact original values.
        row = _rows(csv_text)[1]
        self.assertEqual(row[0], "A, B, C\n次の行")
        self.assertEqual(row[1], "答え, その他")

    def test_uses_crlf_line_terminator(self):
        csv_text = build_wordholic_csv("表\t裏\tタグ\n")

        self.assertIn("\r\n", csv_text)


class WordHolicEmptyInputTests(unittest.TestCase):
    def test_no_cards_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            build_wordholic_csv("")

        self.assertEqual(str(ctx.exception), "no cards were found for wordholic export")

    def test_only_header_and_blank_lines_raises(self):
        tsv = "\n".join(["#separator:Tab", "#deck:x", "", "  "])

        with self.assertRaises(ValueError) as ctx:
            parse_tsv_cards(tsv)

        self.assertEqual(str(ctx.exception), "no cards were found for wordholic export")


class WordHolicFilenameTests(unittest.TestCase):
    def test_filename_is_sanitized_with_wordholic_suffix(self):
        self.assertEqual(
            build_wordholic_filename("薬理学Ⅲ::消化器/潰瘍"),
            "薬理学Ⅲ_消化器_潰瘍_WordHolic.csv",
        )


class WordHolicApiTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryDownloadStore(expires_in_seconds=1800)
        self.client = TestClient(create_app(store=self.store))

    def test_convert_returns_wordholic_csv_and_filename(self):
        response = self.client.post(
            "/api/convert",
            json={"source": SAMPLE_SOURCE, "create_download_link": False},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["wordholic_filename"], "薬理学Ⅲ_テスト単元_WordHolic.csv")

        rows = _rows(data["wordholic_csv"])
        self.assertEqual(rows[0], WORDHOLIC_HEADER)
        self.assertEqual(len(rows), data["card_count"] + 1)
        for row in rows[1:]:
            self.assertEqual(row[3], "ja-JP")
            self.assertEqual(row[4], "ja-JP")

    def test_wordholic_failure_does_not_break_tsv_conversion(self):
        with mock.patch(
            "src.api.build_wordholic_csv", side_effect=ValueError("boom")
        ):
            response = self.client.post(
                "/api/convert",
                json={"source": SAMPLE_SOURCE, "create_download_link": True},
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # TSV/APKG は成功したまま返る
        self.assertTrue(data["tsv"])
        self.assertIsNotNone(data["downloads"]["apkg"])
        # WordHolic はヘッダーのみへフォールバックし、警告が付く
        self.assertEqual(_rows(data["wordholic_csv"]), [WORDHOLIC_HEADER])
        self.assertTrue(data["warnings"])


if __name__ == "__main__":
    unittest.main()
