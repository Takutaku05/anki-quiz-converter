from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path

import genanki


MODEL_ID = 1886375811


@dataclass(frozen=True)
class ApkgCard:
    front: str
    back: str
    tags: list[str]


def parse_tsv_cards(tsv: str) -> list[ApkgCard]:
    cards: list[ApkgCard] = []
    for line in tsv.splitlines():
        if not line or line.startswith("#"):
            continue

        columns = line.split("\t")
        if len(columns) < 2:
            continue

        tags = columns[2].split() if len(columns) >= 3 else []
        cards.append(ApkgCard(front=columns[0], back=columns[1], tags=tags))

    if not cards:
        raise ValueError("no cards were found for apkg export")
    return cards


def build_apkg_bytes(deck: str, tsv: str) -> bytes:
    deck_id = _stable_int_id(f"deck:{deck}")
    model = genanki.Model(
        MODEL_ID,
        "Anki Quiz Converter Basic",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            },
        ],
    )
    package_deck = genanki.Deck(deck_id, deck)

    for card in parse_tsv_cards(tsv):
        note = genanki.Note(
            model=model,
            fields=[card.front, card.back],
            tags=card.tags,
            guid=_stable_guid(deck, card),
        )
        package_deck.add_note(note)

    with tempfile.NamedTemporaryFile(suffix=".apkg", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        genanki.Package(package_deck).write_to_file(str(temp_path))
        return temp_path.read_bytes()
    finally:
        temp_path.unlink(missing_ok=True)


def _stable_int_id(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2_000_000_000 + 1


def _stable_guid(deck: str, card: ApkgCard) -> str:
    digest = hashlib.sha1(
        "\x1f".join([deck, card.front, card.back, " ".join(card.tags)]).encode("utf-8")
    ).hexdigest()
    return digest
