from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from textadventure.asset_bundler import build_asset_bundle


def test_build_asset_bundle_creates_archive_and_manifest(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    (asset_root / "images").mkdir(parents=True)
    (asset_root / "images" / "logo.png").write_bytes(b"logo")
    (asset_root / "notes.txt").write_text("field guide", encoding="utf-8")

    output_dir = tmp_path / "dist"
    timestamp = datetime(2024, 5, 5, 12, 30, tzinfo=timezone.utc)

    result = build_asset_bundle(asset_root, output_dir, timestamp=timestamp)

    assert result.archive_path.exists()
    assert result.manifest_path.exists()
    assert result.generated_at == timestamp

    # The archive should contain hashed filenames matching the manifest entries.
    with zipfile.ZipFile(result.archive_path) as archive:
        archive_names = sorted(archive.namelist())
        hashed_paths = sorted(asset.hashed_path for asset in result.assets)
        assert archive_names == hashed_paths

    manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest_payload["bundle"] == result.archive_path.name
    assert manifest_payload["generated_at"] == "2024-05-05T12:30:00Z"

    notes_entry = next(asset for asset in result.assets if asset.path == "notes.txt")
    assert notes_entry.size == len("field guide".encode("utf-8"))
    assert notes_entry.content_type == "text/plain"
    assert notes_entry.hashed_path.endswith(".txt")

    logo_entry = next(
        asset for asset in result.assets if asset.path == "images/logo.png"
    )
    assert logo_entry.content_type == "image/png"
    assert logo_entry.hashed_path.startswith("images/")
    assert logo_entry.hashed_path.endswith(".png")


def test_build_asset_bundle_can_preserve_filenames(tmp_path: Path) -> None:
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    (asset_root / "manual.pdf").write_bytes(b"pdf")

    output_dir = tmp_path / "dist"
    timestamp = datetime(2024, 5, 1, 9, 0, tzinfo=timezone.utc)

    result = build_asset_bundle(
        asset_root,
        output_dir,
        timestamp=timestamp,
        hashed_naming=False,
        bundle_name="assets.zip",
        manifest_name="manifest.json",
    )

    assert result.archive_path.name == "assets.zip"
    with zipfile.ZipFile(result.archive_path) as archive:
        assert archive.namelist() == ["manual.pdf"]

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["generated_at"] == "2024-05-01T09:00:00Z"
    assert payload["assets"][0]["hashed_path"] == "manual.pdf"


def test_build_asset_bundle_requires_directory(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    with pytest.raises(ValueError):
        build_asset_bundle(missing_root, tmp_path)

    file_root = tmp_path / "not_a_directory.txt"
    file_root.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        build_asset_bundle(file_root, tmp_path)
