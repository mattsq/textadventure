from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from textadventure.api.backup import BackupUploadMetadata, S3BackupUploader


class _StubS3Client:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def test_s3_backup_uploader_puts_object_with_expected_metadata() -> None:
    client = _StubS3Client()
    metadata = BackupUploadMetadata(
        filename="scene-backup-20240701T103000Z-deadbeef.json",
        version_id="20240701T103000Z-deadbeef",
        checksum="abcd1234",
        generated_at=datetime(2024, 7, 1, 10, 30, tzinfo=timezone.utc),
    )

    uploader = S3BackupUploader(bucket="my-bucket", prefix="backups", client=client)
    uploader.upload(content=b"{}", metadata=metadata)

    assert client.calls == [
        {
            "Bucket": "my-bucket",
            "Key": "backups/scene-backup-20240701T103000Z-deadbeef.json",
            "Body": b"{}",
            "ContentType": "application/json",
            "Metadata": {
                "checksum": metadata.checksum,
                "version_id": metadata.version_id,
                "generated_at": metadata.generated_at.isoformat(),
            },
        }
    ]


def test_s3_backup_uploader_merges_custom_options() -> None:
    client = _StubS3Client()
    metadata = BackupUploadMetadata(
        filename="scene-backup-20240701T103000Z-cafebabe.json",
        version_id="20240701T103000Z-cafebabe",
        checksum="feedface",
        generated_at=datetime(2024, 7, 1, 10, 30, tzinfo=timezone.utc),
    )

    uploader = S3BackupUploader(
        bucket="archive",
        prefix="/snapshots/",
        client=client,
        content_type="application/x-json-stream",
        base_metadata={"environment": "staging"},
        extra_put_object_args={"StorageClass": "STANDARD_IA"},
    )
    uploader.upload(content=b"[]", metadata=metadata)

    assert client.calls == [
        {
            "Bucket": "archive",
            "Key": "snapshots/scene-backup-20240701T103000Z-cafebabe.json",
            "Body": b"[]",
            "ContentType": "application/x-json-stream",
            "Metadata": {
                "environment": "staging",
                "checksum": metadata.checksum,
                "version_id": metadata.version_id,
                "generated_at": metadata.generated_at.isoformat(),
            },
            "StorageClass": "STANDARD_IA",
        }
    ]
