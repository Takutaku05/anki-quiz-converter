#!/usr/bin/env python3
"""tests/fixtures/sample_quiz_ja.pdf を再生成するための開発専用スクリプト。

reportlab はテスト実行には不要（requirements.txt にも含めない）。
フィクスチャPDFを作り直したいときだけ手動で実行する::

    python3 -m pip install reportlab
    python3 tests/fixtures/make_sample_pdf.py

生成される PDF には日本語のテキスト層が埋め込まれ、pypdf で抽出できる。
本文は quiz_converter.convert_text がパースできる書式に合わせてある。
"""

from __future__ import annotations

import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

FONT_NAME = "HeiseiKakuGo-W5"  # reportlab同梱のCIDフォント。フォントファイル不要。

LINES = [
    "薬理学Ⅲ（テスト単元）演習問題解答",
    "",
    "第109回 問1",
    "1. レボセチリジンは、くしゃみを抑制する。（○）",
    "2. クロモグリク酸は、CysLT1受容体を遮断する。（×）",
]


def main() -> None:
    out_path = os.path.join(os.path.dirname(__file__), "sample_quiz_ja.pdf")
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    pdf = canvas.Canvas(out_path, pagesize=A4)
    pdf.setFont(FONT_NAME, 14)
    _, height = A4
    y = height - 80
    for line in LINES:
        pdf.drawString(60, y, line)
        y -= 28
    pdf.showPage()
    pdf.save()
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
