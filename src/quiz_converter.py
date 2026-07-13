#!/usr/bin/env python3
"""Convert pharmacology answer text into Anki TSV quiz cards.

The public entry point is ``convert`` (returns deck/TSV/warnings) or the
legacy ``convert_text`` (TSV only).  File input and output can be decided
later; the small CLI exists only for quick local verification.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field


ANKI_HEADER_PREFIX = [
    "#separator:Tab",
    "#html:true",
    "#notetype:Basic",
]

DEFAULT_DECK = "変換デッキ"
MAX_FALLBACK_TITLE_LENGTH = 50

NOTEBOOKLM_URL_RE = re.compile(r"https?://lh3\.googleusercontent\.com/notebooklm/\S+")
ANY_URL_RE = re.compile(r"https?://\S+")
TITLE_RE = re.compile(
    r"(?m)^\s*(?P<course>.+?)\s*[（(]\s*(?P<topic>[^）)]+?)\s*[）)]\s*演習問題解答"
)
GENERIC_TITLE_RE = re.compile(
    r"(?m)^\s*(?P<course>[^\n（()）]{1,40}?)\s*[（(]\s*(?P<topic>[^）)\n]{1,40}?)\s*[）)]"
    r"\s*(?:演習問題解答|演習問題|問題解答|問題集|解答|問題|小テスト|確認テスト|まとめ|テスト)?\s*$"
)
QUESTION_RE = re.compile(
    r"(?:(?<!予想)問題|設問|問|間|(?<![A-Za-z0-9])[QＱ])\s*(?P<number>[0-9０-９]+)\s*[\.．]?"
)
ITEM_RE = re.compile(
    r"(?m)(?:(?<!\S)(?P<number_dot>[0-9０-９]{1,2})\s*[\.．]\s*"
    r"|(?:^|\n|(?<=回)|(?<=[)）]))[ \t　]*(?P<number_plain>[0-9０-９]{1,2})\s+)"
)
ROUND_RE = re.compile(r"第\s*(?P<round>[0-9０-９](?:\s*[0-9０-９])*)\s*回?")

# Answer markers, tried in order.  Earlier patterns are less ambiguous.
ANSWER_MARK = r"[○〇◯⚪×✕✖]"
ANSWER_PATTERNS = [
    re.compile(rf"[\(（]\s*(?P<answer>{ANSWER_MARK})\s*[\)）]"),
    re.compile(r"[\(（]\s*(?P<answer>正解|正|誤り|誤)\s*[\)）]"),
    re.compile(rf"(?:答え|答|正解|解答)\s*[:：]?\s*(?P<answer>{ANSWER_MARK}|正解|正|誤り|誤)"),
    re.compile(rf"(?P<answer>{ANSWER_MARK})\s*$"),
]

FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
CIRCLE_ANSWERS = {"○", "〇", "◯", "⚪", "正", "正解"}
CROSS_ANSWERS = {"×", "✕", "✖", "誤", "誤り"}

WARNING_TITLE_FALLBACK = (
    "タイトル形式を判定できなかったため、デッキ名に「{deck}」を使用しました。"
)
WARNING_TITLE_DEFAULT = (
    f"タイトルを検出できなかったため、デッキ名に「{DEFAULT_DECK}」を使用しました。"
)
WARNING_NO_QUESTION_BLOCKS = (
    "問題番号（問1など）が見つからなかったため、問番号のタグなしで変換しました。"
)
WARNING_LINE_BASED_ITEMS = (
    "番号付きの選択肢が見つからなかった箇所は、行ごとに文と解答を判定しました。"
)


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


@dataclass(frozen=True)
class ConversionResult:
    deck: str
    tsv: str
    warnings: list[str] = field(default_factory=list)


def convert(source: str) -> ConversionResult:
    """Convert source text into deck name, Anki TSV and conversion warnings."""

    cleaned = remove_ignored_urls(source)
    deck, deck_warnings = extract_deck_flexible(cleaned)
    cards, card_warnings = parse_cards_flexible(cleaned)

    lines = [
        *ANKI_HEADER_PREFIX,
        f"#deck:{deck}",
        "#tags column:3",
    ]
    lines.extend(f"{card.statement}\t{card.answer}\t{card.tag}" for card in cards)
    tsv = "\n".join(lines) + "\n"
    return ConversionResult(deck=deck, tsv=tsv, warnings=[*deck_warnings, *card_warnings])


def convert_text(source: str) -> str:
    """Return Anki-compatible TSV text for the given source text."""

    return convert(source).tsv


def remove_ignored_urls(text: str) -> str:
    """Remove NotebookLM image URLs and other standalone URL artifacts."""

    without_notebooklm = NOTEBOOKLM_URL_RE.sub(" ", text)
    return ANY_URL_RE.sub(" ", without_notebooklm)


def extract_deck(text: str) -> str:
    """Extract ``course::topic`` from the strict title line (legacy API)."""

    match = TITLE_RE.search(text)
    if not match:
        raise ValueError("deck name could not be extracted from the title")

    course = normalize_spaces(match.group("course"))
    topic = normalize_spaces(match.group("topic"))
    return f"{course}::{topic}"


def extract_deck_flexible(text: str) -> tuple[str, list[str]]:
    """Extract a deck name, falling back gracefully for unknown title formats.

    Priority: strict ``…（…）演習問題解答`` line, then a generic
    ``course（topic）`` heading near the top, then the first meaningful line,
    then a fixed default deck name.
    """

    match = TITLE_RE.search(text)
    if match:
        course = normalize_spaces(match.group("course"))
        topic = normalize_spaces(match.group("topic"))
        return f"{course}::{topic}", []

    # Pick the first line that reads like a heading (not a numbered item or an
    # answer line), then try to split it into course（topic）.
    title_line = first_meaningful_line(document_head(text))
    if not title_line:
        return DEFAULT_DECK, [WARNING_TITLE_DEFAULT]

    match = GENERIC_TITLE_RE.match(title_line)
    if match:
        course = normalize_spaces(match.group("course"))
        topic = normalize_spaces(match.group("topic"))
        if course and topic:
            return f"{course}::{topic}", []

    return title_line, [WARNING_TITLE_FALLBACK.format(deck=title_line)]


def document_head(text: str) -> str:
    """Return the part of the text before the first question block."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    match = QUESTION_RE.search(normalized)
    if match:
        return normalized[: match.start()]
    return "\n".join(normalized.split("\n")[:15])


def first_meaningful_line(head: str) -> str:
    """Pick the first line that looks like a document title, not an item."""

    for line in head.split("\n"):
        candidate = normalize_spaces(line)
        if not candidate:
            continue
        if re.match(r"^[0-9０-９]{1,3}\s*(?:[\.．]|\s)", candidate):
            continue
        if re.match(r"^第\s*[0-9０-９]", candidate):
            continue
        if find_answer(candidate):
            continue
        return candidate[:MAX_FALLBACK_TITLE_LENGTH]
    return ""


def parse_cards(text: str) -> list[QuizCard]:
    """Parse all numbered true/false statements from the source text."""

    return parse_cards_flexible(text)[0]


def parse_cards_flexible(text: str) -> tuple[list[QuizCard], list[str]]:
    """Parse cards, tolerating missing question blocks and unnumbered items."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    warnings: list[str] = []
    question_matches = list(QUESTION_RE.finditer(normalized))

    sections: list[tuple[str | None, int, str]] = []
    if question_matches:
        for index, question_match in enumerate(question_matches):
            section_start = question_match.start()
            section_end = (
                question_matches[index + 1].start()
                if index + 1 < len(question_matches)
                else len(normalized)
            )
            sections.append(
                (
                    normalize_number(question_match.group("number")),
                    section_start,
                    normalized[section_start:section_end],
                )
            )
    else:
        sections.append((None, 0, normalized))
        warnings.append(WARNING_NO_QUESTION_BLOCKS)

    cards: list[QuizCard] = []
    used_line_fallback = False
    for question_number, section_start, section in sections:
        section_round_number = extract_round(section)
        is_prediction = "以下は予想問題" in normalized[max(0, section_start - 20) : section_start]

        items = parse_items(section)
        if not items:
            items = parse_items_by_line(section)
            if items:
                used_line_fallback = True

        for item in items:
            round_number = item.round_number or section_round_number
            tag = build_tag(question_number, round_number, is_prediction)
            cards.append(QuizCard(statement=item.statement, answer=item.answer, tag=tag))

    if used_line_fallback:
        warnings.append(WARNING_LINE_BASED_ITEMS)

    if not cards:
        raise ValueError("no answer choices were found")
    return cards, warnings


def extract_round(section: str) -> str | None:
    match = ROUND_RE.search(section)
    if not match:
        return None
    return normalize_number(match.group("round"))


def build_tag(question_number: str | None, round_number: str | None, is_prediction: bool) -> str:
    parts: list[str] = []
    if round_number:
        parts.append(f"第{round_number}回")
    elif is_prediction:
        parts.append("予想問題")
    if question_number:
        parts.append(f"問{question_number}")
    return " ".join(parts)


def find_answer(text: str) -> re.Match[str] | None:
    """Locate the answer marker in an item text, trying patterns in order."""

    for pattern in ANSWER_PATTERNS:
        match = pattern.search(text)
        if match:
            return match
    return None


def parse_items(section: str) -> list[ParsedItem]:
    item_matches = list(ITEM_RE.finditer(section))
    items: list[ParsedItem] = []

    for index, item_match in enumerate(item_matches):
        item_start = item_match.end()
        item_end = item_matches[index + 1].start() if index + 1 < len(item_matches) else len(section)
        item = build_item(section[item_start:item_end])
        if item:
            items.append(item)

    return items


def parse_items_by_line(section: str) -> list[ParsedItem]:
    """Fallback: treat each line holding an answer marker as one statement."""

    items: list[ParsedItem] = []
    for line in section.split("\n"):
        item = build_item(line)
        if item:
            items.append(item)
    return items


def build_item(item_text: str) -> ParsedItem | None:
    answer_match = find_answer(item_text)
    if not answer_match:
        return None

    statement = normalize_statement(item_text[: answer_match.start()])
    if not statement:
        return None

    trailing_text = item_text[answer_match.end() :]
    item_round_number = extract_round(trailing_text)
    trailing_text = ROUND_RE.sub(" ", trailing_text)
    trailing_text = trailing_text.replace("以下は予想問題", " ")
    note = normalize_note(trailing_text)
    if note:
        statement = f"{statement}<br><br>{note}"

    answer = normalize_answer(answer_match.group("answer"))
    return ParsedItem(statement=statement, answer=answer, round_number=item_round_number)


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
    compacted = compacted.replace("\uf06d", "μ")
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

    result = convert(source)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    sys.stdout.write(result.tsv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
