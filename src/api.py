from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .apkg_builder import build_apkg_bytes
from .api_helpers import build_download_filename, count_tsv_cards, japanese_error_message
from .quiz_converter import convert_text, extract_deck, remove_ignored_urls
from .r2_storage import DownloadLink, R2DownloadStore


class ConvertRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=1_000_000)
    create_download_link: bool = True


class Downloads(BaseModel):
    tsv: DownloadLink | None = None
    apkg: DownloadLink | None = None


class ConvertResponse(BaseModel):
    deck: str
    card_count: int
    tsv: str
    tsv_filename: str
    apkg_filename: str
    downloads: Downloads
    warnings: list[str]


class CapabilitiesResponse(BaseModel):
    apkg_download_links_enabled: bool
    link_ttl_seconds: int | None


def create_app() -> FastAPI:
    app = FastAPI(title="Anki Quiz Converter", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/capabilities", response_model=CapabilitiesResponse)
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            apkg_download_links_enabled=_r2_settings_available(),
            link_ttl_seconds=_r2_link_ttl_seconds() if _r2_settings_available() else None,
        )

    @app.post("/api/convert", response_model=ConvertResponse)
    def convert(request: ConvertRequest) -> ConvertResponse:
        try:
            cleaned = remove_ignored_urls(request.source)
            deck = extract_deck(cleaned)
            tsv = convert_text(request.source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=japanese_error_message(exc)) from exc

        tsv_filename = build_download_filename(deck, "tsv")
        apkg_filename = build_download_filename(deck, "apkg")
        warnings: list[str] = []
        apkg_link: DownloadLink | None = None

        if request.create_download_link:
            store = R2DownloadStore.from_env()
            if store is None:
                warnings.append(
                    "R2設定が未設定のため、期限付きダウンロードリンクは作成されませんでした。"
                )
            else:
                apkg_link = store.upload_download(
                    content=build_apkg_bytes(deck, tsv),
                    filename=apkg_filename,
                    content_type="application/octet-stream",
                )

        return ConvertResponse(
            deck=deck,
            card_count=count_tsv_cards(tsv),
            tsv=tsv,
            tsv_filename=tsv_filename,
            apkg_filename=apkg_filename,
            downloads=Downloads(apkg=apkg_link),
            warnings=warnings,
        )

    return app


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _r2_settings_available() -> bool:
    return all(
        os.environ.get(key)
        for key in [
            "R2_ACCOUNT_ID",
            "R2_ACCESS_KEY_ID",
            "R2_SECRET_ACCESS_KEY",
            "R2_BUCKET_NAME",
        ]
    )


def _r2_link_ttl_seconds() -> int:
    return int(os.environ.get("R2_LINK_TTL_SECONDS", str(60 * 60 * 24)))


app = create_app()
