from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

WORDHOLIC_MISSING_CARDS_MESSAGE = "no cards were found for wordholic export"


WORDHOLIC_HEADER = ["FrontText", "BackText", "Comment", "FrontTextLanguage", "BackTextLanguage"]
HTML_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass(frozen=True)
class WordHolicCard:
    front: str
    back: str
    comment: str


def build_wordholic_csv(tsv: str) -> str:
    cards = parse_tsv_cards(tsv)
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(WORDHOLIC_HEADER)
    for card in cards:
        writer.writerow([card.front, card.back, card.comment, "ja-JP", "ja-JP"])
    return output.getvalue()


def parse_tsv_cards(tsv: str) -> list[WordHolicCard]:
    cards: list[WordHolicCard] = []

    # Anki TSV (#html:true) is raw tab-separated text without CSV quoting, so a
    # literal " must stay literal. Split on tabs directly instead of using a CSV
    # reader, which would treat quotes as field delimiters and corrupt the data.
    for line in tsv.splitlines():
        if not line or line.startswith("#"):
            continue

        columns = line.split("\t")
        if len(columns) < 2 or not columns[0]:
            continue

        comment = columns[2] if len(columns) >= 3 else ""
        cards.append(
            WordHolicCard(
                front=_to_plain_text(columns[0]),
                back=_to_plain_text(columns[1]),
                comment=_to_plain_text(comment),
            )
        )

    if not cards:
        raise ValueError(WORDHOLIC_MISSING_CARDS_MESSAGE)
    return cards


def _to_plain_text(text: str) -> str:
    return HTML_BREAK_RE.sub("\n", text)
