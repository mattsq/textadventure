from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from textadventure.api import SceneApiSettings, create_app


def _write_user(
    root: Path,
    identifier: str,
    *,
    display_name: str,
    email: str | None = None,
    bio: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> None:
    timestamp = created_at or datetime(2024, 1, 1, tzinfo=timezone.utc)
    updated = updated_at or timestamp

    payload: dict[str, object] = {
        "id": identifier,
        "display_name": display_name,
        "created_at": timestamp.isoformat(),
        "updated_at": updated.isoformat(),
    }
    if email is not None:
        payload["email"] = email
    if bio is not None:
        payload["bio"] = bio

    root.mkdir(parents=True, exist_ok=True)
    with (root / f"{identifier}.json").open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)


def test_list_users_returns_profiles_sorted(tmp_path: Path) -> None:
    created = datetime(2024, 5, 1, 12, 30, tzinfo=timezone.utc)
    _write_user(tmp_path, "alpha", display_name="Alpha", created_at=created)
    _write_user(
        tmp_path,
        "beta",
        display_name="Beta",
        email="beta@example.com",
        bio="Beta bio",
        created_at=created,
        updated_at=created,
    )

    settings = SceneApiSettings(user_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/users")
    assert response.status_code == 200

    payload = response.json()
    assert [entry["id"] for entry in payload["data"]] == ["alpha", "beta"]
    assert payload["data"][1]["email"] == "beta@example.com"
    assert payload["data"][1]["bio"] == "Beta bio"


def test_create_user_persists_profile(tmp_path: Path) -> None:
    settings = SceneApiSettings(user_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.post(
        "/api/users",
        json={
            "id": "Editor",
            "display_name": "Lead Editor",
            "email": "editor@example.com",
            "bio": "Primary editor",
        },
    )
    assert response.status_code == 201

    payload = response.json()
    assert payload["id"] == "editor"
    assert payload["display_name"] == "Lead Editor"
    assert payload["email"] == "editor@example.com"
    assert payload["bio"] == "Primary editor"

    stored_path = tmp_path / "editor.json"
    with stored_path.open("r", encoding="utf-8") as handle:
        stored = json.load(handle)

    assert stored["id"] == "editor"
    assert stored["display_name"] == "Lead Editor"
    assert stored["email"] == "editor@example.com"
    assert stored["bio"] == "Primary editor"
    created_at = datetime.fromisoformat(stored["created_at"])
    updated_at = datetime.fromisoformat(stored["updated_at"])
    assert updated_at >= created_at


def test_update_user_replaces_fields_and_clears_optional(tmp_path: Path) -> None:
    created = datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)
    _write_user(
        tmp_path,
        "writer",
        display_name="Writer",
        email="writer@example.com",
        bio="Writes lore",
        created_at=created,
        updated_at=created,
    )

    settings = SceneApiSettings(user_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/users/writer",
        json={"display_name": "Lead Writer", "bio": None},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["display_name"] == "Lead Writer"
    assert payload["email"] == "writer@example.com"
    assert payload["bio"] is None
    updated_at = datetime.fromisoformat(payload["updated_at"])
    created_at = datetime.fromisoformat(payload["created_at"])
    assert updated_at >= created_at

    with (tmp_path / "writer.json").open("r", encoding="utf-8") as handle:
        stored = json.load(handle)

    assert stored["display_name"] == "Lead Writer"
    assert stored["email"] == "writer@example.com"
    assert "bio" not in stored


def test_users_endpoints_disabled_without_root(tmp_path: Path) -> None:
    settings = SceneApiSettings()
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/users")
    assert response.status_code == 404


def test_get_user_returns_400_for_invalid_identifier(tmp_path: Path) -> None:
    settings = SceneApiSettings(user_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/users/INVALID@ID!")
    assert response.status_code == 400
