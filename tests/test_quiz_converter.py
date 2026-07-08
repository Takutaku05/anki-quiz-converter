import unittest

from src.quiz_converter import convert_text
from sample_data import SAMPLE_SOURCE, SAMPLE_TSV


class QuizConverterTests(unittest.TestCase):
    def test_convert_text_matches_example_output(self):
        self.assertEqual(convert_text(SAMPLE_SOURCE), SAMPLE_TSV)

    def test_convert_text_reports_missing_deck_title(self):
        with self.assertRaisesRegex(ValueError, "deck name could not be extracted"):
            convert_text("問1\n1. テスト文（○）")

    def test_convert_text_reports_missing_question_blocks(self):
        with self.assertRaisesRegex(ValueError, "no question blocks were found"):
            convert_text("薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答\n1. テスト文（○）")

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


if __name__ == "__main__":
    unittest.main()
