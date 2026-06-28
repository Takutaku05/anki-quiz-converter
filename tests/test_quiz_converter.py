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


if __name__ == "__main__":
    unittest.main()
