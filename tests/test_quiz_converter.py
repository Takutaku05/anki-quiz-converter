import unittest

from src.quiz_converter import (
    DEFAULT_DECK,
    WARNING_LINE_BASED_ITEMS,
    WARNING_NO_QUESTION_BLOCKS,
    WARNING_TITLE_DEFAULT,
    convert,
    convert_text,
    extract_deck,
)
from sample_data import SAMPLE_SOURCE, SAMPLE_TSV


class QuizConverterTests(unittest.TestCase):
    def test_convert_text_matches_example_output(self):
        self.assertEqual(convert_text(SAMPLE_SOURCE), SAMPLE_TSV)

    def test_convert_reports_no_warnings_for_strict_format(self):
        result = convert(SAMPLE_SOURCE)

        self.assertEqual(result.deck, "薬理学Ⅲ::テスト単元")
        self.assertEqual(result.warnings, [])

    def test_extract_deck_still_requires_strict_title(self):
        with self.assertRaisesRegex(ValueError, "deck name could not be extracted"):
            extract_deck("問1\n1. テスト文（○）")

    def test_convert_reports_missing_answers(self):
        with self.assertRaisesRegex(ValueError, "no answer choices were found"):
            convert_text("薬理学Ⅲ（テスト）演習問題解答\n問1\n1. 解答記号がない文")

    def test_convert_text_normalizes_spaced_round_digits_from_pdf(self):
        source = """薬理学Ⅲ（抗炎症薬）演習問題解答
問1 正しいものに○ 誤っているものに×を記せ。第1 0 5回
1. ガストリン受容体の刺激（×）
問2 正しいものに○ 誤っているものに×を記せ。第 103 回
1. ロキソプロフェンは、プロドラッグである。（○）
問3 正しいものに○ 誤っているものに×を記せ。第9 9回
1. セレコキシブは、COX-2を選択的に阻害する。（×）
"""

        tsv = convert_text(source)

        self.assertIn("ガストリン受容体の刺激\t×\t第105回 問1", tsv)
        self.assertIn("ロキソプロフェンは、プロドラッグである。\t○\t第103回 問2", tsv)
        self.assertIn("セレコキシブは、COX-2を選択的に阻害する。\t×\t第99回 問3", tsv)

    # --- flexible title detection -------------------------------------

    def test_generic_title_without_keyword_becomes_deck(self):
        source = """生化学（糖代謝）
問1
1. 解糖系はミトコンドリアで進行する。（×）
"""

        result = convert(source)

        self.assertEqual(result.deck, "生化学::糖代謝")
        self.assertEqual(result.warnings, [])

    def test_first_line_used_as_deck_when_no_paren_title(self):
        source = """微生物学まとめノート
問1
1. 大腸菌はグラム陰性桿菌である。（○）
"""

        result = convert(source)

        self.assertEqual(result.deck, "微生物学まとめノート")
        self.assertTrue(any("微生物学まとめノート" in w for w in result.warnings))

    def test_default_deck_when_no_usable_title(self):
        source = """問1
1. 心臓は筋肉でできている。（○）
"""

        result = convert(source)

        self.assertEqual(result.deck, DEFAULT_DECK)
        self.assertIn(WARNING_TITLE_DEFAULT, result.warnings)

    # --- flexible question / answer detection -------------------------

    def test_cards_without_question_blocks(self):
        source = """生理学（循環）
1. 心臓は筋肉でできている。（○）
2. 動脈は静脈より薄い。（×）
"""

        result = convert(source)

        self.assertIn(WARNING_NO_QUESTION_BLOCKS, result.warnings)
        self.assertIn("心臓は筋肉でできている。\t○\t", result.tsv)
        self.assertIn("動脈は静脈より薄い。\t×\t", result.tsv)

    def test_setsumon_and_q_prefixes_are_detected(self):
        source = """薬理学（自律神経）演習問題解答
設問1
1. アドレナリンはα受容体を刺激する。（○）
Q2
1. アトロピンはムスカリン受容体を遮断する。（○）
"""

        result = convert(source)

        self.assertIn("アドレナリンはα受容体を刺激する。\t○\t問1", result.tsv)
        self.assertIn("アトロピンはムスカリン受容体を遮断する。\t○\t問2", result.tsv)

    def test_word_answer_markers_are_normalized(self):
        source = """病理学（炎症）演習問題解答
問1
1. 急性炎症では好中球が主体である。（正）
2. 慢性炎症は数時間で消失する。（誤）
"""

        result = convert(source)

        self.assertIn("急性炎症では好中球が主体である。\t○\t問1", result.tsv)
        self.assertIn("慢性炎症は数時間で消失する。\t×\t問1", result.tsv)

    def test_line_based_fallback_for_unnumbered_items(self):
        source = """解剖学（骨格）演習問題解答
問1
上腕骨は上肢の骨である。（○）
大腿骨は下肢の骨である。（○）
"""

        result = convert(source)

        self.assertIn(WARNING_LINE_BASED_ITEMS, result.warnings)
        self.assertIn("上腕骨は上肢の骨である。\t○\t問1", result.tsv)
        self.assertIn("大腿骨は下肢の骨である。\t○\t問1", result.tsv)

    def test_answer_prefix_style_is_detected(self):
        source = """公衆衛生（統計）演習問題解答
問1
1. 平均値は外れ値の影響を受ける。 答え：○
"""

        result = convert(source)

        self.assertIn("平均値は外れ値の影響を受ける。\t○\t問1", result.tsv)


if __name__ == "__main__":
    unittest.main()
