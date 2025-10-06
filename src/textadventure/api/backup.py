"""Cloud backup helpers for scene datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, cast


class _S3ClientProtocol(Protocol):
    def put_object(self, **kwargs: Any) -> Any:
        """Persist an object to S3."""


@dataclass(frozen=True)
class BackupUploadMetadata:
    """Metadata describing a backup payload pushed to external storage."""

    filename: str
    version_id: str
    checksum: str
    generated_at: datetime


class BackupUploader(Protocol):
    """Protocol for uploading scene backups to external storage providers."""

    def upload(self, *, content: bytes, metadata: BackupUploadMetadata) -> None:
        """Persist the backup ``content`` using ``metadata`` for labelling."""


class S3BackupUploader:
    """Upload backups to an Amazon S3 compatible bucket."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str | None = None,
        client: _S3ClientProtocol | None = None,
        region_name: str | None = None,
        endpoint_url: str | None = None,
        content_type: str = "application/json",
        base_metadata: Mapping[str, str] | None = None,
        extra_put_object_args: Mapping[str, Any] | None = None,
    ) -> None:
        self._bucket = bucket
        normalised_prefix = (prefix or "").strip()
        self._prefix = normalised_prefix.strip("/")
        self._content_type = content_type
        self._base_metadata = dict(base_metadata or {})
        self._extra_put_object_args = dict(extra_put_object_args or {})
        self._client: _S3ClientProtocol

        if client is not None:
            self._client = client
            return

        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(
                "boto3 is required to use S3BackupUploader but is not installed."
            ) from exc

        self._client = cast(
            _S3ClientProtocol,
            boto3.client("s3", region_name=region_name, endpoint_url=endpoint_url),
        )

    def upload(self, *, content: bytes, metadata: BackupUploadMetadata) -> None:
        key = (
            metadata.filename
            if not self._prefix
            else f"{self._prefix}/{metadata.filename}"
        )

        metadata_map = {**self._base_metadata}
        metadata_map["checksum"] = metadata.checksum
        metadata_map["version_id"] = metadata.version_id
        metadata_map["generated_at"] = metadata.generated_at.isoformat()

        put_kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": content,
            "ContentType": self._content_type,
            "Metadata": metadata_map,
        }
        put_kwargs.update(self._extra_put_object_args)

        self._client.put_object(**put_kwargs)


__all__ = [
    "BackupUploadMetadata",
    "BackupUploader",
    "S3BackupUploader",
]
