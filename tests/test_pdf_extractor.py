import io
import os
import unittest

from pypdf import PdfWriter

from src.pdf_extractor import (
    CorruptPdfError,
    EncryptedPdfError,
    NoTextLayerError,
    TooManyPagesError,
    collapse_cjk_spaces,
    extract_pdf_text,
)

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SAMPLE_PDF = os.path.join(FIXTURE_DIR, "sample_quiz_ja.pdf")


def _blank_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _encrypted_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    # RC4はcryptographyバックエンドなしで扱えるため、CIで追加依存が不要。
    writer.encrypt(user_password="secret", algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class CollapseCjkSpacesTests(unittest.TestCase):
    def test_removes_space_between_cjk(self):
        self.assertEqual(collapse_cjk_spaces("レ ボ セ チリジン"), "レボセチリジン")

    def test_keeps_space_between_alnum_and_cjk(self):
        self.assertEqual(collapse_cjk_spaces("H1 受容体"), "H1 受容体")


class ExtractPdfTextTests(unittest.TestCase):
    def test_extracts_japanese_text(self):
        with open(SAMPLE_PDF, "rb") as handle:
            result = extract_pdf_text(handle.read())

        self.assertGreaterEqual(result.page_count, 1)
        self.assertIn("レボセチリジン", result.text)
        self.assertIn("演習問題解答", result.text)

    def test_empty_pdf_raises_no_text_layer(self):
        with self.assertRaises(NoTextLayerError):
            extract_pdf_text(_blank_pdf_bytes())

    def test_encrypted_pdf_raises(self):
        with self.assertRaises(EncryptedPdfError):
            extract_pdf_text(_encrypted_pdf_bytes())

    def test_corrupt_pdf_raises(self):
        with self.assertRaises(CorruptPdfError):
            extract_pdf_text(b"%PDF-1.4 not really a pdf")

    def test_too_many_pages_raises(self):
        with self.assertRaises(TooManyPagesError):
            extract_pdf_text(_blank_pdf_bytes(), max_pages=0)


if __name__ == "__main__":
    unittest.main()
