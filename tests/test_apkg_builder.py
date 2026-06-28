import unittest
import zipfile

from src.apkg_builder import build_apkg_bytes, parse_tsv_cards


class ApkgBuilderTests(unittest.TestCase):
    def test_parse_tsv_cards_reads_front_back_and_tags(self):
        cards = parse_tsv_cards(
            "\n".join(
                [
                    "#separator:Tab",
                    "#html:true",
                    "問題文<br>続き\t○\t第109回 問1",
                    "別問題\t×\t予想問題 問2",
                ]
            )
        )

        self.assertEqual(cards[0].front, "問題文<br>続き")
        self.assertEqual(cards[0].back, "○")
        self.assertEqual(cards[0].tags, ["第109回", "問1"])
        self.assertEqual(cards[1].tags, ["予想問題", "問2"])

    def test_build_apkg_bytes_creates_anki_package_zip(self):
        apkg = build_apkg_bytes(
            deck="薬理学Ⅲ::テスト",
            tsv="\n".join(
                [
                    "#separator:Tab",
                    "#html:true",
                    "問題文\t○\t第109回 問1",
                ]
            ),
        )

        self.assertTrue(apkg.startswith(b"PK"))
        with zipfile.ZipFile(__import__("io").BytesIO(apkg)) as package:
            names = set(package.namelist())

        self.assertIn("collection.anki2", names)
        self.assertIn("media", names)


if __name__ == "__main__":
    unittest.main()
