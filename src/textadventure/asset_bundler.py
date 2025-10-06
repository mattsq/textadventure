"""Utilities for packaging project assets for production deployments."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class BundledAsset:
    """Metadata describing a single asset included in a bundle."""

    path: str
    hashed_path: str
    size: int
    checksum: str
    content_type: str | None
    updated_at: datetime


@dataclass(frozen=True)
class AssetBundleResult:
    """Information about an asset bundle and its generated metadata."""

    root: Path
    generated_at: datetime
    archive_path: Path
    manifest_path: Path
    assets: list[BundledAsset]


__all__ = [
    "AssetBundleResult",
    "BundledAsset",
    "build_asset_bundle",
    "main",
]


def build_asset_bundle(
    root: Path,
    output: Path,
    *,
    hashed_naming: bool = True,
    timestamp: datetime | None = None,
    bundle_name: str | None = None,
    manifest_name: str = "assets-manifest.json",
) -> AssetBundleResult:
    """Package ``root`` into a ZIP archive and emit a manifest describing its files."""

    root_path = Path(root)
    if not root_path.exists():
        raise ValueError(f"Asset root '{root_path}' does not exist.")
    if not root_path.is_dir():
        raise ValueError(f"Asset root '{root_path}' must be a directory.")

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    generated_at = _normalise_timestamp(timestamp)
    if bundle_name is None:
        bundle_name = f"assets-{generated_at.strftime('%Y%m%dT%H%M%SZ')}.zip"

    archive_path = output_path / bundle_name
    manifest_path = output_path / manifest_name

    files = sorted(_iter_files(root_path))
    assets: list[BundledAsset] = []

    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for file_path in files:
            relative_path = file_path.relative_to(root_path)
            checksum = _compute_checksum(file_path)
            hashed_relative = (
                _hashed_relative_path(relative_path, checksum)
                if hashed_naming
                else relative_path.as_posix()
            )

            archive.write(file_path, arcname=hashed_relative)

            stat = file_path.stat()
            updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            content_type, _ = mimetypes.guess_type(file_path.name)
            assets.append(
                BundledAsset(
                    path=relative_path.as_posix(),
                    hashed_path=hashed_relative,
                    size=stat.st_size,
                    checksum=checksum,
                    content_type=content_type,
                    updated_at=updated_at,
                )
            )

    assets.sort(key=lambda asset: asset.path)

    manifest_payload = {
        "root": root_path.name,
        "generated_at": _format_timestamp(generated_at),
        "bundle": archive_path.name,
        "assets": [
            {
                "path": asset.path,
                "hashed_path": asset.hashed_path,
                "size": asset.size,
                "checksum": asset.checksum,
                "content_type": asset.content_type,
                "updated_at": _format_timestamp(asset.updated_at),
            }
            for asset in assets
        ],
    }

    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    return AssetBundleResult(
        root=root_path,
        generated_at=generated_at,
        archive_path=archive_path,
        manifest_path=manifest_path,
        assets=assets,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for building asset bundles."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = build_asset_bundle(
            Path(args.root),
            Path(args.output),
            hashed_naming=not args.preserve_filenames,
            timestamp=args.timestamp,
            bundle_name=args.bundle_name,
            manifest_name=args.manifest_name,
        )
    except Exception as exc:  # pragma: no cover - exercised via CLI errors
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Wrote {len(result.assets)} assets to {result.archive_path.name} "
        f"(manifest: {result.manifest_path.name})"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bundle project assets into a versioned archive with a manifest.",
    )
    parser.add_argument(
        "--root", required=True, help="Directory containing project assets."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where the bundle archive and manifest will be written.",
    )
    parser.add_argument(
        "--bundle-name",
        help="Optional filename for the generated bundle archive. Defaults to a timestamped name.",
    )
    parser.add_argument(
        "--manifest-name",
        default="assets-manifest.json",
        help="Filename for the generated manifest. Defaults to 'assets-manifest.json'.",
    )
    parser.add_argument(
        "--preserve-filenames",
        action="store_true",
        help="Store original filenames in the archive instead of hashed variants.",
    )
    parser.add_argument(
        "--timestamp",
        type=_parse_timestamp,
        help=(
            "Override the timestamp used for naming and manifest metadata. "
            "Accepts ISO-8601 strings (defaults to the current UTC time)."
        ),
    )
    return parser


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Timestamp must be an ISO-8601 string (e.g., 2024-05-05T12:30:00Z)."
        ) from exc
    return _normalise_timestamp(parsed)


def _normalise_timestamp(timestamp: datetime | None) -> datetime:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return timestamp.replace(microsecond=0)


def _iter_files(root: Path) -> Iterable[Path]:
    for current_root, _, filenames in os.walk(root):
        current_path = Path(current_root)
        for filename in sorted(filenames):
            file_path = current_path / filename
            if file_path.is_file():
                yield file_path


def _compute_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hashed_relative_path(relative_path: Path, checksum: str) -> str:
    parent = relative_path.parent
    suffix = relative_path.suffix
    if suffix:
        stem = relative_path.name[: -len(suffix)]
        filename = f"{stem}.{checksum[:8]}{suffix}"
    else:
        filename = f"{relative_path.name}.{checksum[:8]}"
    if parent == Path("."):
        return filename
    return (parent / filename).as_posix()


def _format_timestamp(value: datetime) -> str:
    value = _normalise_timestamp(value)
    return value.isoformat().replace("+00:00", "Z")


if __name__ == "__main__":  # pragma: no cover - module executable
    raise SystemExit(main())
