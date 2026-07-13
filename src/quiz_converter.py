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
    r"(?:(?m:^[ \t　]*(?P<problem_label>問題))"
    r"|(?P<label>設問|問|間|(?<![A-Za-z0-9])[QＱ]))"
    r"\s*(?P<number>[0-9０-９]+)\s*[\.．]?"
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
ANSWER_INSTRUCTION_RE = re.compile(
    r"(?:正しい|正解|誤(?:って|り)|間違).*[○〇◯⚪].*[×✕✖]"
    r"|[○〇◯⚪].*[×✕✖].*(?:記せ|付け|つけ|選べ)"
)

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

    # Prefer a course（topic） heading anywhere near the top. Documents often
    # put metadata such as the school year on the line before the real title.
    title_lines = meaningful_lines(document_head(text))
    if not title_lines:
        return DEFAULT_DECK, [WARNING_TITLE_DEFAULT]

    for title_line in title_lines:
        match = GENERIC_TITLE_RE.match(title_line)
        if match:
            course = normalize_spaces(match.group("course"))
            topic = normalize_spaces(match.group("topic"))
            if course and topic:
                return f"{course}::{topic}", []

    title_line = title_lines[0]
    return title_line, [WARNING_TITLE_FALLBACK.format(deck=title_line)]


def document_head(text: str) -> str:
    """Return the part of the text before the first question block."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    match = QUESTION_RE.search(normalized)
    if match:
        return normalized[: match.start()]
    return "\n".join(normalized.split("\n")[:15])


def meaningful_lines(head: str) -> list[str]:
    """Return plausible heading lines from a document head."""

    lines: list[str] = []
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
        lines.append(candidate[:MAX_FALLBACK_TITLE_LENGTH])
    return lines


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
            section_start = question_label_start(question_match)
            section_end = (
                question_label_start(question_matches[index + 1])
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

        items, section_used_line_fallback = parse_items_flexible(section)
        used_line_fallback = used_line_fallback or section_used_line_fallback

        for item in items:
            round_number = item.round_number or section_round_number
            tag = build_tag(question_number, round_number, is_prediction)
            cards.append(QuizCard(statement=item.statement, answer=item.answer, tag=tag))

    if used_line_fallback:
        warnings.append(WARNING_LINE_BASED_ITEMS)

    if not cards:
        raise ValueError("no answer choices were found")
    return cards, warnings


def question_label_start(match: re.Match[str]) -> int:
    """Return the start of the actual question label for either regex branch."""

    if match.group("problem_label") is not None:
        return match.start("problem_label")
    return match.start("label")


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


def parse_items_flexible(section: str) -> tuple[list[ParsedItem], bool]:
    """Parse numbered items and answer-bearing unnumbered lines in source order.

    ``numbered_matches`` is sorted by position, so a single forward-moving index
    is enough to find, for each line, whether a marker ends on it and which
    marker precedes it.  This keeps the scan linear in the input size.
    """

    numbered_matches = list(ITEM_RE.finditer(section))
    candidates: list[tuple[int, int, bool]] = [
        (match.start(), match.end(), False) for match in numbered_matches
    ]

    next_index = 0
    previous_numbered_match: re.Match[str] | None = None
    line_start = 0
    for line_with_ending in section.splitlines(keepends=True):
        line = line_with_ending.rstrip("\r\n")
        line_end = line_start + len(line)

        # Advance past every marker that ended on or before this line's start;
        # the last such marker is the one this line may continue.
        while next_index < len(numbered_matches) and numbered_matches[next_index].end() <= line_start:
            previous_numbered_match = numbered_matches[next_index]
            next_index += 1

        has_numbered_marker = (
            next_index < len(numbered_matches)
            and numbered_matches[next_index].end() <= line_end
        )
        continues_numbered_item = (
            previous_numbered_match is not None
            and find_answer(section[previous_numbered_match.end() : line_start]) is None
        )
        if (
            not has_numbered_marker
            and not continues_numbered_item
            and find_answer(line)
            and not is_answer_instruction(line)
            and not QUESTION_RE.match(line)
        ):
            candidates.append((line_start, line_start, True))
        line_start += len(line_with_ending)

    candidates.sort(key=lambda candidate: candidate[0])
    items: list[ParsedItem] = []
    used_line_fallback = False
    for index, (_, content_start, is_line_fallback) in enumerate(candidates):
        content_end = candidates[index + 1][0] if index + 1 < len(candidates) else len(section)
        item = build_item(section[content_start:content_end])
        if item:
            items.append(item)
            used_line_fallback = used_line_fallback or is_line_fallback

    return items, used_line_fallback


def is_answer_instruction(line: str) -> bool:
    """Return whether a line explains how to mark answers rather than being a card."""

    return bool(ANSWER_INSTRUCTION_RE.search(normalize_spaces(line)))


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
