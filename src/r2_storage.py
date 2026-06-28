from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable, Protocol
from urllib.parse import quote


class S3Client(Protocol):
    def put_object(self, **kwargs) -> object:
        ...

    def generate_presigned_url(self, client_method: str, Params: dict, ExpiresIn: int) -> str:
        ...


@dataclass(frozen=True)
class R2Settings:
    bucket_name: str
    public_prefix: str = "generated"
    expires_in_seconds: int = 60 * 60 * 24


@dataclass(frozen=True)
class DownloadLink:
    url: str
    filename: str
    expires_at: str
    expires_in_seconds: int


class R2DownloadStore:
    def __init__(
        self,
        settings: R2Settings,
        client: S3Client,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.now = now or (lambda: datetime.now(UTC))

    @classmethod
    def from_env(cls) -> "R2DownloadStore | None":
        bucket_name = os.environ.get("R2_BUCKET_NAME")
        access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
        secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        account_id = os.environ.get("R2_ACCOUNT_ID")

        if not all([bucket_name, access_key_id, secret_access_key, account_id]):
            return None

        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("boto3 is required when R2 settings are configured") from exc

        endpoint_url = os.environ.get(
            "R2_ENDPOINT_URL",
            f"https://{account_id}.r2.cloudflarestorage.com",
        )
        expires_in_seconds = int(os.environ.get("R2_LINK_TTL_SECONDS", str(60 * 60 * 24)))
        public_prefix = os.environ.get("R2_PUBLIC_PREFIX", "generated")

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )
        return cls(
            settings=R2Settings(
                bucket_name=bucket_name,
                public_prefix=public_prefix.strip("/") or "generated",
                expires_in_seconds=expires_in_seconds,
            ),
            client=client,
        )

    def upload_download(self, content: bytes, filename: str, content_type: str) -> DownloadLink:
        key = self._build_key(filename)
        self.client.put_object(
            Bucket=self.settings.bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
            ContentDisposition=f"attachment; filename*=UTF-8''{quote(filename)}",
        )
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.bucket_name, "Key": key},
            ExpiresIn=self.settings.expires_in_seconds,
        )
        expires_at = self.now() + timedelta(seconds=self.settings.expires_in_seconds)
        return DownloadLink(
            url=url,
            filename=filename,
            expires_at=expires_at.isoformat(),
            expires_in_seconds=self.settings.expires_in_seconds,
        )

    def _build_key(self, filename: str) -> str:
        suffix = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        return f"{self.settings.public_prefix}/{uuid.uuid4().hex}.{suffix}"
