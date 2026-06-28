from pathlib import Path
import unittest


from src.quiz_converter import convert_text


ROOT = Path(__file__).resolve().parents[1]


class QuizConverterTests(unittest.TestCase):
    def test_convert_text_matches_example_output(self):
        source = (ROOT / "example" / "sauce" / "アレルギー疾患治療薬.txt").read_text(
            encoding="utf-8"
        )
        expected = (ROOT / "example" / "output" / "アレルギー疾患治療薬.tsv").read_text(
            encoding="utf-8"
        )

        self.assertEqual(convert_text(source), expected)

    def test_convert_text_reports_missing_deck_title(self):
        with self.assertRaisesRegex(ValueError, "deck name could not be extracted"):
            convert_text("問1\n1. テスト文（○）")

    def test_convert_text_reports_missing_question_blocks(self):
        with self.assertRaisesRegex(ValueError, "no question blocks were found"):
            convert_text("薬理学Ⅲ（アレルギー疾患治療薬）演習問題解答\n1. テスト文（○）")


if __name__ == "__main__":
    unittest.main()
