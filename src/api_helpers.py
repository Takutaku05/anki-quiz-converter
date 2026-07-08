from __future__ import annotations

import re

from .pdf_extractor import EncryptedPdfError, NoTextLayerError, TooManyPagesError


def japanese_error_message(error: Exception) -> str:
    message = str(error)
    if "deck name could not be extracted" in message:
        return "タイトルからデッキ名を抽出できません。"
    if "no question blocks were found" in message:
        return "問題ブロックが見つかりません。"
    if "no answer choices were found" in message:
        return "解答選択肢が見つかりません。"
    if "unsupported answer marker" in message:
        return "対応していない解答記号が含まれています。"
    return "変換に失敗しました。入力内容を確認してください。"


def pdf_error_message(error: Exception) -> str:
    if isinstance(error, EncryptedPdfError):
        return (
            "パスワード付き（暗号化された）PDFには対応していません。"
            "パスワードを解除してからアップロードしてください。"
        )
    if isinstance(error, NoTextLayerError):
        return (
            "PDFから文字を抽出できませんでした。"
            "画像として保存されたPDF（スキャンや写真）には対応していません。"
            "文字が埋め込まれたPDFをご利用ください。"
        )
    if isinstance(error, TooManyPagesError):
        return "ページ数が多すぎます。50ページ以下のPDFをアップロードしてください。"
    return "PDFを読み取れませんでした。ファイルが壊れていないか確認してください。"


def count_tsv_cards(tsv: str) -> int:
    return sum(1 for line in tsv.splitlines() if line and not line.startswith("#"))


def build_download_filename(deck: str, extension: str) -> str:
    safe_name = re.sub(r'[\\/:*?"<>|\s]+', "_", deck).strip("._")
    if not safe_name:
        safe_name = "anki_cards"
    return f"{safe_name}.{extension.lstrip('.')}"


def build_wordholic_filename(deck: str) -> str:
    return build_download_filename(f"{deck}_WordHolic", "csv")
