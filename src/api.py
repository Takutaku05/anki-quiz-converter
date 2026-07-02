from __future__ import annotations

import os
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .apkg_builder import build_apkg_bytes
from .api_helpers import build_download_filename, count_tsv_cards, japanese_error_message
from .download_store import DownloadLink, InMemoryDownloadStore
from .quiz_converter import convert_text, extract_deck, remove_ignored_urls


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


def create_app(store: InMemoryDownloadStore | None = None) -> FastAPI:
    app = FastAPI(title="Anki Quiz Converter", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    download_store = store or InMemoryDownloadStore.from_env()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/capabilities", response_model=CapabilitiesResponse)
    def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            apkg_download_links_enabled=True,
            link_ttl_seconds=download_store.expires_in_seconds,
        )

    @app.post("/api/convert", response_model=ConvertResponse)
    def convert(request: ConvertRequest, http_request: Request) -> ConvertResponse:
        try:
            cleaned = remove_ignored_urls(request.source)
            deck = extract_deck(cleaned)
            tsv = convert_text(request.source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=japanese_error_message(exc)) from exc

        tsv_filename = build_download_filename(deck, "tsv")
        apkg_filename = build_download_filename(deck, "apkg")
        apkg_link: DownloadLink | None = None

        if request.create_download_link:
            token, expires_at = download_store.put(
                content=build_apkg_bytes(deck, tsv),
                filename=apkg_filename,
                content_type="application/octet-stream",
            )
            apkg_link = DownloadLink(
                url=f"{_public_base_url(http_request)}/api/download/{token}",
                filename=apkg_filename,
                expires_at=expires_at.isoformat(),
                expires_in_seconds=download_store.expires_in_seconds,
            )

        return ConvertResponse(
            deck=deck,
            card_count=count_tsv_cards(tsv),
            tsv=tsv,
            tsv_filename=tsv_filename,
            apkg_filename=apkg_filename,
            downloads=Downloads(apkg=apkg_link),
            warnings=[],
        )

    @app.get("/api/download/{token}")
    def download(token: str) -> Response:
        stored = download_store.get(token)
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail="リンクが無効か、有効期限が切れています。もう一度変換してください。",
            )
        return Response(
            content=stored.content,
            media_type=stored.content_type,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(stored.filename)}",
                "Cache-Control": "no-store",
            },
        )

    return app


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _public_base_url(request: Request) -> str:
    configured = os.environ.get("PUBLIC_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


app = create_app()
