from __future__ import annotations

import os
import secrets
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable


@dataclass(frozen=True)
class DownloadLink:
    url: str
    filename: str
    expires_at: str
    expires_in_seconds: int


@dataclass(frozen=True)
class StoredFile:
    content: bytes
    filename: str
    content_type: str
    expires_at: datetime


class InMemoryDownloadStore:
    """変換結果の.apkgをサーバーメモリに短時間だけ保持するストア。

    Render無料プランはスリープでメモリが消えるため、リンクは短命前提。
    """

    def __init__(
        self,
        expires_in_seconds: int = 60 * 30,
        max_entries: int = 100,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.expires_in_seconds = expires_in_seconds
        self.max_entries = max_entries
        self.now = now or (lambda: datetime.now(UTC))
        self._entries: OrderedDict[str, StoredFile] = OrderedDict()

    @classmethod
    def from_env(cls) -> "InMemoryDownloadStore":
        expires_in_seconds = int(os.environ.get("DOWNLOAD_LINK_TTL_SECONDS", str(60 * 30)))
        max_entries = int(os.environ.get("DOWNLOAD_MAX_ENTRIES", "100"))
        return cls(expires_in_seconds=expires_in_seconds, max_entries=max_entries)

    def put(self, content: bytes, filename: str, content_type: str) -> tuple[str, datetime]:
        self._purge_expired()
        while len(self._entries) >= self.max_entries:
            self._entries.popitem(last=False)

        token = secrets.token_urlsafe(16)
        expires_at = self.now() + timedelta(seconds=self.expires_in_seconds)
        self._entries[token] = StoredFile(
            content=content,
            filename=filename,
            content_type=content_type,
            expires_at=expires_at,
        )
        return token, expires_at

    def get(self, token: str) -> StoredFile | None:
        self._purge_expired()
        return self._entries.get(token)

    def _purge_expired(self) -> None:
        current = self.now()
        expired = [token for token, entry in self._entries.items() if entry.expires_at <= current]
        for token in expired:
            del self._entries[token]
