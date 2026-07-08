from __future__ import annotations

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PAGES = 50

# ひらがな・カタカナ・CJK統合漢字・全角英数記号・和文約物。
_CJK = r"　-ヿ㐀-䶿一-鿿＀-￯"
_CJK_SPACE_RE = re.compile(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])")


class PdfExtractionError(Exception):
    """PDFからのテキスト抽出に失敗したことを表す基底例外。"""


class EncryptedPdfError(PdfExtractionError):
    """パスワード付き（暗号化）PDF。"""


class CorruptPdfError(PdfExtractionError):
    """壊れているか読み取れないPDF。"""


class TooManyPagesError(PdfExtractionError):
    """ページ数が上限を超えているPDF。"""


class NoTextLayerError(PdfExtractionError):
    """テキスト層を持たないPDF（スキャン画像など）。"""


@dataclass(frozen=True)
class PdfExtractionResult:
    text: str
    page_count: int


def collapse_cjk_spaces(text: str) -> str:
    # 抽出時にCJK文字の間へ混入するスペースだけを除去する。
    # 「H1 受容体」のような英数字とCJKの境界のスペースは保持する。
    return _CJK_SPACE_RE.sub("", text)


def extract_pdf_text(data: bytes, *, max_pages: int = MAX_PAGES) -> PdfExtractionResult:
    try:
        reader = PdfReader(io.BytesIO(data))
    except PdfReadError as exc:
        raise CorruptPdfError(str(exc)) from exc

    if reader.is_encrypted:
        raise EncryptedPdfError("encrypted pdf")

    try:
        page_count = len(reader.pages)
    except PdfReadError as exc:
        raise CorruptPdfError(str(exc)) from exc
    if page_count > max_pages:
        raise TooManyPagesError(f"too many pages: {page_count} > {max_pages}")

    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:  # pypdfは特殊なフォントで多様な例外を投げうる
            raise CorruptPdfError(str(exc)) from exc

    text = collapse_cjk_spaces("\n".join(parts)).strip()
    if not text:
        raise NoTextLayerError("no text layer")
    return PdfExtractionResult(text=text, page_count=page_count)
