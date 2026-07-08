#!/usr/bin/env python3
"""Convert pharmacology answer text into Anki TSV quiz cards.

The public entry point is ``convert_text``.  File input and output can be
decided later; the small CLI exists only for quick local verification.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass


ANKI_HEADER_PREFIX = [
    "#separator:Tab",
    "#html:true",
    "#notetype:Basic",
]

NOTEBOOKLM_URL_RE = re.compile(r"https?://lh3\.googleusercontent\.com/notebooklm/\S+")
ANY_URL_RE = re.compile(r"https?://\S+")
TITLE_RE = re.compile(
    r"(?m)^\s*(?P<course>.+?)\s*[（(]\s*(?P<topic>[^）)]+?)\s*[）)]\s*演習問題解答"
)
QUESTION_RE = re.compile(r"(?:問|間)\s*(?P<number>[0-9０-９]+)\s*[\.．]?")
ITEM_RE = re.compile(
    r"(?m)(?:(?<!\S)(?P<number_dot>[0-9０-９]{1,2})\s*[\.．]\s*"
    r"|(?:^|\n|(?<=回)|(?<=[)）]))[ \t　]*(?P<number_plain>[0-9０-９]{1,2})\s+)"
)
ROUND_RE = re.compile(r"第\s*(?P<round>[0-9０-９](?:\s*[0-9０-９])*)\s*回?")
ANSWER_RE = re.compile(r"[\(（]\s*(?P<answer>[○〇◯⚪×✕✖])\s*[\)）]")

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
CIRCLE_ANSWERS = {"○", "〇", "◯", "⚪"}
CROSS_ANSWERS = {"×", "✕", "✖"}


@dataclass(frozen=True)
class QuizCard:
    statement: str
    answer: str
    tag: str


@dataclass(frozen=True)
class ParsedItem:
    statement: str
    answer: str
    round_number: str | None = None


def convert_text(source: str) -> str:
    """Return Anki-compatible TSV text for the given source text."""

    cleaned = remove_ignored_urls(source)
    deck = extract_deck(cleaned)
    cards = parse_cards(cleaned)

    lines = [
        *ANKI_HEADER_PREFIX,
        f"#deck:{deck}",
        "#tags column:3",
    ]
    lines.extend(f"{card.statement}\t{card.answer}\t{card.tag}" for card in cards)
    return "\n".join(lines) + "\n"


def remove_ignored_urls(text: str) -> str:
    """Remove NotebookLM image URLs and other standalone URL artifacts."""

    without_notebooklm = NOTEBOOKLM_URL_RE.sub(" ", text)
    return ANY_URL_RE.sub(" ", without_notebooklm)


def extract_deck(text: str) -> str:
    """Extract ``course::topic`` from the title line."""

    match = TITLE_RE.search(text)
    if not match:
        raise ValueError("deck name could not be extracted from the title")

    course = normalize_spaces(match.group("course"))
    topic = normalize_spaces(match.group("topic"))
    return f"{course}::{topic}"


def parse_cards(text: str) -> list[QuizCard]:
    """Parse all numbered true/false statements from the source text."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    question_matches = list(QUESTION_RE.finditer(normalized))
    if not question_matches:
        raise ValueError("no question blocks were found")

    cards: list[QuizCard] = []
    for index, question_match in enumerate(question_matches):
        section_start = question_match.start()
        section_end = (
            question_matches[index + 1].start()
            if index + 1 < len(question_matches)
            else len(normalized)
        )
        section = normalized[section_start:section_end]
        question_number = normalize_number(question_match.group("number"))
        section_round_number = extract_round(section)
        is_prediction = "以下は予想問題" in normalized[max(0, section_start - 20) : section_start]

        for item in parse_items(section):
            round_number = item.round_number or section_round_number
            tag = build_tag(question_number, round_number, is_prediction)
            cards.append(QuizCard(statement=item.statement, answer=item.answer, tag=tag))

    if not cards:
        raise ValueError("no answer choices were found")
    return cards


def extract_round(section: str) -> str | None:
    match = ROUND_RE.search(section)
    if not match:
        return None
    return normalize_number(match.group("round"))


def build_tag(question_number: str, round_number: str | None, is_prediction: bool) -> str:
    if round_number:
        return f"第{round_number}回 問{question_number}"
    if is_prediction:
        return f"予想問題 問{question_number}"
    return f"問{question_number}"


def parse_items(section: str) -> list[ParsedItem]:
    item_matches = list(ITEM_RE.finditer(section))
    items: list[ParsedItem] = []

    for index, item_match in enumerate(item_matches):
        item_start = item_match.end()
        item_end = item_matches[index + 1].start() if index + 1 < len(item_matches) else len(section)
        item_text = section[item_start:item_end]

        answer_match = ANSWER_RE.search(item_text)
        if not answer_match:
            continue

        statement = normalize_statement(item_text[: answer_match.start()])
        if not statement:
            continue

        trailing_text = item_text[answer_match.end() :]
        item_round_number = extract_round(trailing_text)
        trailing_text = ROUND_RE.sub(" ", trailing_text)
        trailing_text = trailing_text.replace("以下は予想問題", " ")
        note = normalize_note(trailing_text)
        if note:
            statement = f"{statement}<br><br>{note}"

        answer = normalize_answer(answer_match.group("answer"))
        items.append(ParsedItem(statement=statement, answer=answer, round_number=item_round_number))

    return items


def normalize_answer(answer: str) -> str:
    stripped = answer.strip().replace("\ufe0e", "").replace("\ufe0f", "")
    if stripped in CIRCLE_ANSWERS:
        return "○"
    if stripped in CROSS_ANSWERS:
        return "×"
    raise ValueError(f"unsupported answer marker: {answer!r}")


def normalize_number(number: str) -> str:
    return re.sub(r"\s+", "", number).translate(FULLWIDTH_DIGITS)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\u3000", " ")).strip()


def normalize_statement(text: str) -> str:
    compacted = normalize_spaces(text)
    compacted = compacted.replace("", "μ")
    compacted = compacted.translate(FULLWIDTH_DIGITS)
    compacted = re.sub(r"\s+", "", compacted)
    return fix_common_ocr_errors(compacted)


def fix_common_ocr_errors(text: str) -> str:
    """Fix narrow OCR errors that would otherwise create duplicate cards."""

    replacements = {
        "αl受容体": "α1受容体",
        "フェキソフエナジン": "フェキソフェナジン",
        "括抗": "拮抗",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    return text


def normalize_note(text: str) -> str:
    cleaned = normalize_spaces(text)
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:註|注|※)+\s*", "", cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:註|注)\s*[:：]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    return f"※註：{cleaned}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert quiz answer text to Anki TSV.")
    parser.add_argument("input", nargs="?", help="source text file. stdin is used when omitted.")
    args = parser.parse_args(argv)

    if args.input:
        with open(args.input, encoding="utf-8") as source_file:
            source = source_file.read()
    else:
        source = sys.stdin.read()

    sys.stdout.write(convert_text(source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
