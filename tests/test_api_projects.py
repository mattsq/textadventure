import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from textadventure.api import SceneApiSettings, create_app
from textadventure.api.app import CURRENT_SCENE_SCHEMA_VERSION, UserAccountStore


def _write_project(
    root: Path,
    identifier: str,
    scenes: Mapping[str, Any],
    *,
    metadata: Mapping[str, Any] | None = None,
    scene_filename: str = "scenes.json",
    timestamp: datetime | None = None,
) -> None:
    directory = root / identifier
    directory.mkdir(parents=True, exist_ok=True)

    scene_path = directory / scene_filename
    with scene_path.open("w", encoding="utf-8") as handle:
        json.dump(scenes, handle)

    metadata_path = directory / "project.json"
    if metadata is not None:
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(dict(metadata), handle)

    if timestamp is not None:
        epoch = timestamp.timestamp()
        os.utime(scene_path, (epoch, epoch))
        if metadata is not None:
            os.utime(metadata_path, (epoch, epoch))


def _checksum_and_version(
    scenes: Mapping[str, Any], timestamp: datetime
) -> tuple[str, str]:
    canonical = json.dumps(
        scenes,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    version_prefix = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    version_id = f"{version_prefix}-{checksum[:8]}"
    return checksum, version_id


def _create_user_profile(root: Path, identifier: str, display_name: str) -> None:
    store = UserAccountStore(root=root)
    store.create(identifier=identifier, display_name=display_name)


def test_scene_mutations_enforce_project_collaborator_roles(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting point",
            "choices": [
                {"command": "look", "description": "Survey the room."},
            ],
            "transitions": {
                "look": {
                    "narration": "You take in your surroundings.",
                    "target": "hall",
                }
            },
        },
        "hall": {
            "description": "A quiet hallway",
            "choices": [
                {"command": "return", "description": "Head back."},
            ],
            "transitions": {
                "return": {
                    "narration": "You walk back to the starting point.",
                    "target": "start",
                }
            },
        },
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
                {"user_id": "viewer@example.com", "role": "viewer"},
            ],
        },
    )

    scene_path = tmp_path / "atlas" / "scenes.json"
    settings = SceneApiSettings(
        project_root=tmp_path,
        scene_path=scene_path,
        branch_root=tmp_path / "branches",
    )
    client = TestClient(create_app(settings=settings))

    new_scene = {
        "description": "Hidden cellar",
        "choices": [
            {"command": "wait", "description": "Pause for a moment."},
        ],
        "transitions": {"wait": {"narration": "Time passes quietly.", "target": None}},
    }

    body = {
        "id": "cellar",
        "scene": new_scene,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    missing_context = client.post("/api/scenes", json=body)
    assert missing_context.status_code == 403
    assert "collaborator" in missing_context.json()["detail"].lower()

    viewer_response = client.post(
        "/api/scenes",
        params={"acting_user_id": "viewer@example.com"},
        json=body,
    )
    assert viewer_response.status_code == 403

    editor_response = client.post(
        "/api/scenes",
        params={"acting_user_id": "editor@example.com"},
        json=body,
    )
    assert editor_response.status_code == 201

    persisted = json.loads(scene_path.read_text())
    assert "cellar" in persisted
    assert persisted["cellar"]["description"] == "Hidden cellar"

    branch_payload = {
        "branch_name": "New Path",
        "scenes": {
            "start": {
                "description": "Starting point (branch)",
                "choices": [
                    {"command": "step", "description": "Step forward."},
                ],
                "transitions": {
                    "step": {
                        "narration": "You discover a balcony.",
                        "target": "balcony",
                    }
                },
            },
            "balcony": {
                "description": "An open balcony",
                "choices": [
                    {"command": "rest", "description": "Take a short rest."},
                ],
                "transitions": {
                    "rest": {"narration": "You catch your breath.", "target": None}
                },
            },
        },
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    branch_missing = client.post("/api/scenes/branches", json=branch_payload)
    assert branch_missing.status_code == 403

    branch_viewer = client.post(
        "/api/scenes/branches",
        params={"acting_user_id": "viewer@example.com"},
        json=branch_payload,
    )
    assert branch_viewer.status_code == 403

    branch_owner = client.post(
        "/api/scenes/branches",
        params={"acting_user_id": "owner@example.com"},
        json=branch_payload,
    )
    assert branch_owner.status_code == 201

    branch_id = branch_owner.json()["id"]

    delete_unauthorised = client.delete(
        f"/api/scenes/branches/{branch_id}",
        params={"acting_user_id": "viewer@example.com"},
    )
    assert delete_unauthorised.status_code == 403

    delete_authorised = client.delete(
        f"/api/scenes/branches/{branch_id}",
        params={"acting_user_id": "owner@example.com"},
    )
    assert delete_authorised.status_code == 204


def test_list_projects_returns_registered_metadata(tmp_path: Path) -> None:
    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    alpha_scenes: dict[str, Any] = {
        "alpha": {
            "description": "Alpha start",
            "choices": [
                {"command": "continue", "description": "Continue onward."},
            ],
            "transitions": {
                "continue": {
                    "narration": "You move forward.",
                    "target": "beta",
                }
            },
        },
        "beta": {
            "description": "Beta room",
            "choices": [
                {"command": "return", "description": "Head back."},
            ],
            "transitions": {
                "return": {
                    "narration": "You return to the start.",
                    "target": "alpha",
                }
            },
        },
    }

    beta_scenes: dict[str, Any] = {
        "intro": {
            "description": "Intro scene",
            "choices": [
                {"command": "explore", "description": "Look around."},
            ],
            "transitions": {
                "explore": {
                    "narration": "You explore the area.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "alpha",
        alpha_scenes,
        metadata={
            "name": "Alpha Project",
            "description": "First project.",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {
                    "user_id": "editor@example.com",
                    "role": "editor",
                    "display_name": "Lead Editor",
                },
            ],
        },
        timestamp=timestamp,
    )
    _write_project(
        tmp_path,
        "beta",
        beta_scenes,
        metadata={"name": "Beta Project", "scene_path": "custom.json"},
        scene_filename="custom.json",
        timestamp=timestamp,
    )

    checksum_alpha, version_alpha = _checksum_and_version(alpha_scenes, timestamp)
    checksum_beta, version_beta = _checksum_and_version(beta_scenes, timestamp)

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects")
    assert response.status_code == 200

    payload = response.json()
    projects = {entry["id"]: entry for entry in payload["data"]}
    assert set(projects) == {"alpha", "beta"}

    alpha = projects["alpha"]
    assert alpha["name"] == "Alpha Project"
    assert alpha["description"] == "First project."
    assert alpha["scene_count"] == len(alpha_scenes)
    assert alpha["collaborator_count"] == 2
    assert alpha["checksum"] == checksum_alpha
    assert alpha["version_id"] == version_alpha
    assert datetime.fromisoformat(alpha["updated_at"]) == timestamp
    assert datetime.fromisoformat(alpha["created_at"]) == timestamp

    beta = projects["beta"]
    assert beta["name"] == "Beta Project"
    assert beta.get("description") is None
    assert beta["scene_count"] == len(beta_scenes)
    assert beta["collaborator_count"] == 0
    assert beta["checksum"] == checksum_beta
    assert beta["version_id"] == version_beta


def test_get_project_returns_scene_payload(tmp_path: Path) -> None:
    timestamp = datetime(2024, 6, 1, tzinfo=timezone.utc)
    scenes: dict[str, Any] = {
        "hub": {
            "description": "Central hub",
            "choices": [
                {"command": "north", "description": "Go north."},
            ],
            "transitions": {
                "north": {
                    "narration": "You walk north.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "hub",
        scenes,
        metadata={"name": "Hub Project"},
        timestamp=timestamp,
    )

    checksum, version_id = _checksum_and_version(scenes, timestamp)

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects/hub")
    assert response.status_code == 200

    payload = response.json()
    assert payload["data"]["id"] == "hub"
    assert payload["data"]["checksum"] == checksum
    assert payload["data"]["version_id"] == version_id
    assert payload["data"]["collaborator_count"] == 0
    assert payload["scenes"] == scenes


def test_export_project_returns_zip_archive(tmp_path: Path) -> None:
    timestamp = datetime(2024, 5, 1, 10, tzinfo=timezone.utc)
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting point",
            "choices": [
                {"command": "north", "description": "Head north."},
            ],
            "transitions": {
                "north": {
                    "narration": "You walk into the forest.",
                    "target": "clearing",
                }
            },
        },
        "clearing": {
            "description": "A quiet clearing",
            "choices": [
                {"command": "rest", "description": "Take a short rest."},
            ],
            "transitions": {
                "rest": {
                    "narration": "You feel refreshed.",
                    "target": None,
                }
            },
        },
    }

    metadata = {"name": "Atlas Migration", "description": "Adventure export"}

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata=metadata,
        timestamp=timestamp,
    )

    assets_root = tmp_path / "atlas" / "assets"
    (assets_root / "images").mkdir(parents=True, exist_ok=True)
    (assets_root / "empty").mkdir(parents=True, exist_ok=True)

    logo_bytes = b"\x89PNG"
    (assets_root / "images" / "logo.png").write_bytes(logo_bytes)

    notes_text = "Remember the hidden door."
    (assets_root / "notes.txt").write_text(notes_text, encoding="utf-8")

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects/atlas/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    checksum, version_id = _checksum_and_version(scenes, timestamp)
    disposition = response.headers["content-disposition"]
    assert f'filename="atlas-project-export-{version_id}.zip"' in disposition
    assert response.headers["x-textadventure-project-id"] == "atlas"
    assert response.headers["x-textadventure-project-version"] == version_id
    assert response.headers["x-textadventure-project-checksum"] == checksum

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = sorted(archive.namelist())
        assert names == [
            "atlas/",
            "atlas/assets/",
            "atlas/assets/empty/",
            "atlas/assets/images/",
            "atlas/assets/images/logo.png",
            "atlas/assets/notes.txt",
            "atlas/project.json",
            "atlas/scenes.json",
        ]

        assert json.loads(archive.read("atlas/scenes.json").decode("utf-8")) == scenes
        assert (
            json.loads(archive.read("atlas/project.json").decode("utf-8")) == metadata
        )
        assert archive.read("atlas/assets/images/logo.png") == logo_bytes
        assert archive.read("atlas/assets/notes.txt").decode("utf-8") == notes_text


def test_list_project_assets_returns_files_and_directories(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={"name": "Atlas"},
        timestamp=datetime(2024, 5, 1, tzinfo=timezone.utc),
    )

    assets_root = tmp_path / "atlas" / "assets"
    (assets_root / "images").mkdir(parents=True, exist_ok=True)

    logo_bytes = b"\x89PNG"
    logo_path = assets_root / "images" / "logo.png"
    with logo_path.open("wb") as handle:
        handle.write(logo_bytes)

    notes_text = "Remember the hidden door."
    notes_path = assets_root / "notes.txt"
    notes_path.write_text(notes_text, encoding="utf-8")

    image_dir_timestamp = datetime(2024, 5, 2, 9, tzinfo=timezone.utc)
    logo_timestamp = datetime(2024, 5, 3, 12, tzinfo=timezone.utc)
    notes_timestamp = datetime(2024, 5, 4, 15, tzinfo=timezone.utc)

    os.utime(logo_path, (logo_timestamp.timestamp(), logo_timestamp.timestamp()))
    os.utime(notes_path, (notes_timestamp.timestamp(), notes_timestamp.timestamp()))
    os.utime(
        assets_root / "images",
        (image_dir_timestamp.timestamp(), image_dir_timestamp.timestamp()),
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects/atlas/assets")
    assert response.status_code == 200

    payload = response.json()
    assert payload["project_id"] == "atlas"
    assert payload["root"] == "assets"

    asset_paths = [asset["path"] for asset in payload["assets"]]
    assert asset_paths == ["images", "notes.txt", "images/logo.png"]

    directory_entry = payload["assets"][0]
    assert directory_entry["type"] == "directory"
    assert directory_entry["size"] is None
    assert directory_entry["content_type"] is None
    assert directory_entry["updated_at"] == image_dir_timestamp.isoformat()

    notes_entry = payload["assets"][1]
    assert notes_entry["type"] == "file"
    assert notes_entry["size"] == len(notes_text.encode("utf-8"))
    assert notes_entry["content_type"] == "text/plain"
    assert notes_entry["updated_at"] == notes_timestamp.isoformat()

    logo_entry = payload["assets"][2]
    assert logo_entry["type"] == "file"
    assert logo_entry["size"] == len(logo_bytes)
    assert logo_entry["content_type"] == "image/png"
    assert logo_entry["updated_at"] == logo_timestamp.isoformat()


def test_get_project_asset_returns_file_content(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    assets_root = tmp_path / "atlas" / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)

    logo_bytes = b"\x89PNG"
    logo_path = assets_root / "images" / "logo.png"
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_bytes(logo_bytes)

    notes_text = "Remember the hidden door."
    (assets_root / "notes.txt").write_text(notes_text, encoding="utf-8")

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects/atlas/assets/images/logo.png")
    assert response.status_code == 200
    assert response.content == logo_bytes
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="logo.png"'

    missing_response = client.get("/api/projects/atlas/assets/images/missing.png")
    assert missing_response.status_code == 404


def test_get_project_asset_rejects_invalid_paths(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )

    assets_root = tmp_path / "atlas" / "assets"
    (assets_root / "images").mkdir(parents=True, exist_ok=True)

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    traversal_response = client.get("/api/projects/atlas/assets/../scenes.json")
    assert traversal_response.status_code == 400

    directory_response = client.get("/api/projects/atlas/assets/images")
    assert directory_response.status_code == 400


def test_upload_project_asset_creates_file(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    payload = b"logo-bytes"
    encoded = base64.b64encode(payload).decode("ascii")
    response = client.put(
        "/api/projects/atlas/assets/images/logo.png",
        params={"acting_user_id": "editor@example.com"},
        json={"content": encoded},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["path"] == "images/logo.png"
    assert body["name"] == "logo.png"
    assert body["type"] == "file"
    assert body["size"] == len(payload)
    assert body["content_type"] == "image/png"
    # Ensure timestamp is returned in ISO format.
    datetime.fromisoformat(body["updated_at"])

    asset_path = tmp_path / "atlas" / "assets" / "images" / "logo.png"
    assert asset_path.exists()
    assert asset_path.read_bytes() == payload

    fetch_response = client.get("/api/projects/atlas/assets/images/logo.png")
    assert fetch_response.status_code == 200
    assert fetch_response.content == payload


def test_upload_project_asset_rejects_invalid_path(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/atlas/assets/../scenes.json",
        params={"acting_user_id": "owner@example.com"},
        json={"content": base64.b64encode(b"{}").decode("ascii")},
    )

    assert response.status_code == 400


def test_upload_project_asset_enforces_collaborator_permissions(
    tmp_path: Path,
) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {"narration": "You look around the room.", "target": None}
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "viewer@example.com", "role": "viewer"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    asset_path = tmp_path / "atlas" / "assets" / "images" / "logo.png"

    encoded = base64.b64encode(b"logo-bytes").decode("ascii")

    missing_context = client.put(
        "/api/projects/atlas/assets/images/logo.png",
        json={"content": encoded},
    )
    assert missing_context.status_code == 403
    assert "collaborator context" in missing_context.json()["detail"]

    viewer_response = client.put(
        "/api/projects/atlas/assets/images/logo.png",
        params={"acting_user_id": "viewer@example.com"},
        json={"content": encoded},
    )
    assert viewer_response.status_code == 403
    assert "permission" in viewer_response.json()["detail"].lower()
    assert not asset_path.exists()


def test_delete_project_asset_removes_file(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    assets_root = tmp_path / "atlas" / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    asset_path = assets_root / "images" / "logo.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"logo")

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.delete(
        "/api/projects/atlas/assets/images/logo.png",
        params={"acting_user_id": "editor@example.com"},
    )
    assert response.status_code == 204
    assert not asset_path.exists()

    missing_response = client.delete(
        "/api/projects/atlas/assets/images/logo.png",
        params={"acting_user_id": "editor@example.com"},
    )
    assert missing_response.status_code == 404


def test_delete_project_asset_removes_directory(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Starting scene",
            "choices": [
                {"command": "look", "description": "Look around."},
            ],
            "transitions": {
                "look": {
                    "narration": "You look around the room.",
                    "target": None,
                }
            },
        }
    }

    _write_project(
        tmp_path,
        "atlas",
        scenes,
        metadata={
            "name": "Atlas",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    assets_root = tmp_path / "atlas" / "assets"
    icon_directory = assets_root / "images" / "icons"
    icon_directory.mkdir(parents=True, exist_ok=True)
    (icon_directory / "logo.png").write_bytes(b"logo")

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.delete(
        "/api/projects/atlas/assets/images/icons",
        params={"acting_user_id": "editor@example.com"},
    )
    assert response.status_code == 204
    assert not icon_directory.exists()


def test_list_project_collaborators_returns_metadata(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "proceed", "description": "Proceed"},
            ],
            "transitions": {"proceed": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "collab",
        scenes,
        metadata={
            "name": "Collaboration",
            "collaborators": [
                {
                    "user_id": "owner@example.com",
                    "role": "owner",
                    "display_name": "Project Owner",
                },
                {"user_id": "viewer@example.com", "role": "viewer"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/projects/collab/collaborators")
    assert response.status_code == 200

    payload = response.json()
    assert payload["project_id"] == "collab"
    assert payload["collaborators"] == [
        {
            "user_id": "owner@example.com",
            "role": "owner",
            "display_name": "Project Owner",
        },
        {
            "user_id": "viewer@example.com",
            "role": "viewer",
            "display_name": None,
        },
    ]


def test_replace_project_collaborators_updates_metadata(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "begin", "description": "Begin"},
            ],
            "transitions": {"begin": {"narration": "Begin", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "editable",
        scenes,
        metadata={
            "name": "Editable",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/editable/collaborators",
        params={"acting_user_id": "owner@example.com"},
        json={
            "collaborators": [
                {
                    "user_id": "owner@example.com",
                    "role": "owner",
                    "display_name": "Owner",
                },
                {"user_id": "editor@example.com", "role": "editor"},
            ]
        },
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["project_id"] == "editable"
    assert payload["collaborators"][0]["user_id"] == "owner@example.com"
    assert payload["collaborators"][1]["user_id"] == "editor@example.com"

    metadata_path = tmp_path / "editable" / "project.json"
    with metadata_path.open("r", encoding="utf-8") as handle:
        stored_metadata = json.load(handle)

    assert stored_metadata["collaborators"] == [
        {
            "user_id": "owner@example.com",
            "role": "owner",
            "display_name": "Owner",
        },
        {"user_id": "editor@example.com", "role": "editor"},
    ]

    project_response = client.get("/api/projects/editable")
    assert project_response.status_code == 200
    assert project_response.json()["data"]["collaborator_count"] == 2


def test_replace_project_collaborators_requires_owner(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "solo",
        scenes,
        metadata={
            "name": "Solo",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/solo/collaborators",
        params={"acting_user_id": "owner@example.com"},
        json={"collaborators": [{"user_id": "viewer@example.com", "role": "viewer"}]},
    )

    assert response.status_code == 400
    assert "owner" in response.json()["detail"]

    metadata_path = tmp_path / "solo" / "project.json"
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        assert metadata["collaborators"] == [
            {"user_id": "owner@example.com", "role": "owner"}
        ]


def test_replace_project_collaborators_requires_existing_users(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    project_root = tmp_path / "projects"
    user_root = tmp_path / "users"

    _write_project(
        project_root,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )
    _create_user_profile(user_root, "owner@example.com", "Owner")

    settings = SceneApiSettings(project_root=project_root, user_root=user_root)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/shared/collaborators",
        params={"acting_user_id": "owner@example.com"},
        json={
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "missing@example.com", "role": "editor"},
            ]
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert "missing@example.com" in payload["detail"]


def test_project_collaborator_display_name_defaults_to_user_profile(
    tmp_path: Path,
) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    project_root = tmp_path / "projects"
    user_root = tmp_path / "users"

    _write_project(
        project_root,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )
    _create_user_profile(user_root, "owner@example.com", "Owner")
    _create_user_profile(user_root, "editor@example.com", "Editor Example")

    settings = SceneApiSettings(project_root=project_root, user_root=user_root)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/shared/collaborators",
        params={"acting_user_id": "owner@example.com"},
        json={
            "collaborators": [
                {
                    "user_id": "owner@example.com",
                    "role": "owner",
                    "display_name": "Owner",
                },
                {"user_id": "editor@example.com", "role": "editor"},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["collaborators"] == [
        {
            "user_id": "owner@example.com",
            "role": "owner",
            "display_name": "Owner",
        },
        {
            "user_id": "editor@example.com",
            "role": "editor",
            "display_name": "Editor Example",
        },
    ]

    list_response = client.get("/api/projects/shared/collaborators")
    assert list_response.status_code == 200
    collaborators = list_response.json()["collaborators"]
    assert collaborators[1]["display_name"] == "Editor Example"


def test_replace_project_collaborators_rejects_non_owner(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/shared/collaborators",
        params={"acting_user_id": "editor@example.com"},
        json={
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
            ]
        },
    )

    assert response.status_code == 403
    assert "required role" in response.json()["detail"].lower()


def test_collaboration_session_lifecycle(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
                {"user_id": "viewer@example.com", "role": "viewer"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    list_response = client.get("/api/projects/shared/collaboration/sessions")
    assert list_response.status_code == 200
    assert list_response.json()["sessions"] == []

    join_response = client.post(
        "/api/projects/shared/collaboration/sessions",
        params={"acting_user_id": "editor@example.com"},
        json={"scene_id": "start", "ttl_seconds": 45},
    )

    assert join_response.status_code == 200
    join_payload = join_response.json()
    assert join_payload["project_id"] == "shared"
    assert len(join_payload["sessions"]) == 1

    created = join_payload["sessions"][0]
    assert created["user_id"] == "editor@example.com"
    assert created["role"] == "editor"
    assert created["scene_id"] == "start"
    assert created["session_id"]
    first_heartbeat = datetime.fromisoformat(created["last_heartbeat"])
    first_expiry = datetime.fromisoformat(created["expires_at"])
    assert first_expiry > first_heartbeat

    session_id = created["session_id"]

    heartbeat_response = client.post(
        "/api/projects/shared/collaboration/sessions",
        params={"acting_user_id": "editor@example.com"},
        json={"session_id": session_id, "scene_id": "hall"},
    )

    assert heartbeat_response.status_code == 200
    heartbeat_payload = heartbeat_response.json()
    assert len(heartbeat_payload["sessions"]) == 1
    updated = heartbeat_payload["sessions"][0]
    assert updated["session_id"] == session_id
    assert updated["scene_id"] == "hall"
    updated_heartbeat = datetime.fromisoformat(updated["last_heartbeat"])
    updated_expiry = datetime.fromisoformat(updated["expires_at"])
    assert updated_heartbeat >= first_heartbeat
    assert updated_expiry >= updated_heartbeat
    assert updated_expiry >= first_expiry

    viewer_delete = client.delete(
        f"/api/projects/shared/collaboration/sessions/{session_id}",
        params={"acting_user_id": "viewer@example.com"},
    )
    assert viewer_delete.status_code == 403

    owner_delete = client.delete(
        f"/api/projects/shared/collaboration/sessions/{session_id}",
        params={"acting_user_id": "owner@example.com"},
    )
    assert owner_delete.status_code == 200
    assert owner_delete.json()["sessions"] == []

    final_list = client.get("/api/projects/shared/collaboration/sessions")
    assert final_list.status_code == 200
    assert final_list.json()["sessions"] == []


def test_collaboration_sessions_purge_expired(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
            ],
        },
    )

    collaboration_path = tmp_path / "shared" / "collaboration.json"
    now = datetime.now(timezone.utc)
    stale_payload = {
        "sessions": [
            {
                "session_id": "stale",
                "user_id": "owner@example.com",
                "scene_id": "start",
                "started_at": (now - timedelta(minutes=5)).isoformat(),
                "last_heartbeat": (now - timedelta(minutes=4)).isoformat(),
                "expires_at": (now - timedelta(minutes=1)).isoformat(),
            }
        ]
    }

    collaboration_path.write_text(json.dumps(stale_payload))

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    purge_response = client.get("/api/projects/shared/collaboration/sessions")
    assert purge_response.status_code == 200
    assert purge_response.json()["sessions"] == []

    persisted_payload = json.loads(collaboration_path.read_text())
    assert persisted_payload["sessions"] == []

    with pytest.raises(ValidationError):
        client.post(
            "/api/projects/shared/collaboration/sessions",
            params={"acting_user_id": "owner@example.com"},
            json={"ttl_seconds": 5},
        )

    assert json.loads(collaboration_path.read_text())["sessions"] == []


def test_scene_comment_thread_lifecycle(tmp_path: Path) -> None:
    scenes: dict[str, Any] = {
        "start": {
            "description": "Start",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    _write_project(
        tmp_path,
        "shared",
        scenes,
        metadata={
            "name": "Shared",
            "collaborators": [
                {"user_id": "owner@example.com", "role": "owner"},
                {"user_id": "editor@example.com", "role": "editor"},
                {"user_id": "viewer@example.com", "role": "viewer"},
            ],
        },
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    list_response = client.get("/api/projects/shared/scenes/start/comments")
    assert list_response.status_code == 200
    assert list_response.json()["threads"] == []

    create_payload = {
        "location": {"type": "transition_narration", "choice_command": "go"},
        "body": "Consider adding more tension to the reveal.",
    }

    missing_actor = client.post(
        "/api/projects/shared/scenes/start/comments",
        json=create_payload,
    )
    assert missing_actor.status_code == 403

    create_response = client.post(
        "/api/projects/shared/scenes/start/comments",
        params={"acting_user_id": "viewer@example.com"},
        json=create_payload,
    )
    assert create_response.status_code == 201
    created_thread = create_response.json()
    assert created_thread["scene_id"] == "start"
    assert created_thread["status"] == "open"
    assert len(created_thread["comments"]) == 1
    assert (
        created_thread["comments"][0]["body"]
        == "Consider adding more tension to the reveal."
    )
    assert created_thread["comments"][0]["author_id"] == "viewer@example.com"

    thread_id = created_thread["id"]

    reply_response = client.post(
        f"/api/projects/shared/scenes/start/comments/{thread_id}/replies",
        params={"acting_user_id": "owner@example.com"},
        json={"body": "Added additional sensory detail to the corridor."},
    )
    assert reply_response.status_code == 201
    replied_thread = reply_response.json()
    assert len(replied_thread["comments"]) == 2
    assert replied_thread["comments"][1]["author_id"] == "owner@example.com"

    resolve_response = client.post(
        f"/api/projects/shared/scenes/start/comments/{thread_id}/resolution",
        params={"acting_user_id": "owner@example.com"},
        json={"resolved": True},
    )
    assert resolve_response.status_code == 200
    resolved_thread = resolve_response.json()
    assert resolved_thread["status"] == "resolved"
    assert resolved_thread["resolved_by"] == "owner@example.com"
    assert resolved_thread["resolved_at"] is not None

    reopen_response = client.post(
        f"/api/projects/shared/scenes/start/comments/{thread_id}/resolution",
        params={"acting_user_id": "editor@example.com"},
        json={"resolved": False},
    )
    assert reopen_response.status_code == 200
    reopened_thread = reopen_response.json()
    assert reopened_thread["status"] == "open"
    assert reopened_thread["resolved_at"] is None
    assert reopened_thread["resolved_by"] is None

    filtered_none = client.get(
        "/api/projects/shared/scenes/start/comments",
        params={"choice_command": "wait"},
    )
    assert filtered_none.status_code == 200
    assert filtered_none.json()["threads"] == []

    filtered_type = client.get(
        "/api/projects/shared/scenes/start/comments",
        params={"location_type": "transition_narration"},
    )
    assert filtered_type.status_code == 200
    assert len(filtered_type.json()["threads"]) == 1

    comments_path = tmp_path / "shared" / "comments.json"
    stored_payload = json.loads(comments_path.read_text())
    assert len(stored_payload["threads"]) == 1
    stored_thread = stored_payload["threads"][0]
    assert stored_thread["scene_id"] == "start"
    assert stored_thread["location"]["choice_command"] == "go"
    assert len(stored_thread["comments"]) == 2
    assert stored_thread["comments"][0]["author_id"] == "viewer@example.com"


def test_projects_endpoints_return_404_when_disabled() -> None:
    client = TestClient(create_app(settings=SceneApiSettings()))

    response = client.get("/api/projects")
    assert response.status_code == 404

    detail_response = client.get("/api/projects/unknown")
    assert detail_response.status_code == 404


def test_list_project_templates_returns_registered_metadata(tmp_path: Path) -> None:
    timestamp = datetime(2024, 2, 1, tzinfo=timezone.utc)

    starter_scenes: dict[str, Any] = {
        "start": {
            "description": "Template opening",
            "choices": [
                {"command": "begin", "description": "Begin your quest."},
            ],
            "transitions": {
                "begin": {
                    "narration": "The journey begins.",
                    "target": None,
                }
            },
        }
    }

    mystery_scenes: dict[str, Any] = {
        "foyer": {
            "description": "A dimly lit foyer.",
            "choices": [
                {"command": "inspect", "description": "Inspect the surroundings."},
            ],
            "transitions": {
                "inspect": {
                    "narration": "You discover a hidden clue.",
                    "target": None,
                }
            },
        }
    }

    template_root = tmp_path / "templates"
    project_root = tmp_path / "projects"

    _write_project(
        template_root,
        "starter",
        starter_scenes,
        metadata={"name": "Starter Kit", "description": "Kick-off adventure."},
        timestamp=timestamp,
    )
    _write_project(
        template_root,
        "mystery",
        mystery_scenes,
        metadata={"name": "Mystery", "scene_path": "mystery.json"},
        scene_filename="mystery.json",
        timestamp=timestamp,
    )

    starter_checksum, _ = _checksum_and_version(starter_scenes, timestamp)
    mystery_checksum, _ = _checksum_and_version(mystery_scenes, timestamp)

    settings = SceneApiSettings(
        project_root=project_root, project_template_root=template_root
    )
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/project-templates")
    assert response.status_code == 200

    payload = response.json()
    templates = {entry["id"]: entry for entry in payload["data"]}

    assert set(templates) == {"mystery", "starter"}

    starter = templates["starter"]
    assert starter["name"] == "Starter Kit"
    assert starter["description"] == "Kick-off adventure."
    assert starter["scene_count"] == len(starter_scenes)
    assert starter["checksum"] == starter_checksum

    mystery = templates["mystery"]
    assert mystery["name"] == "Mystery"
    assert mystery.get("description") is None
    assert mystery["scene_count"] == len(mystery_scenes)
    assert mystery["checksum"] == mystery_checksum


def test_instantiate_project_template_creates_project_directory(tmp_path: Path) -> None:
    timestamp = datetime(2024, 5, 1, tzinfo=timezone.utc)

    scenes: dict[str, Any] = {
        "intro": {
            "description": "Template intro",
            "choices": [
                {"command": "venture", "description": "Venture forth."},
            ],
            "transitions": {
                "venture": {
                    "narration": "You step into the unknown.",
                    "target": None,
                }
            },
        }
    }

    template_root = tmp_path / "templates"
    project_root = tmp_path / "projects"

    _write_project(
        template_root,
        "starter",
        scenes,
        metadata={"name": "Starter", "scene_path": "template.json"},
        scene_filename="template.json",
        timestamp=timestamp,
    )

    checksum, _ = _checksum_and_version(scenes, timestamp)

    settings = SceneApiSettings(
        project_root=project_root, project_template_root=template_root
    )
    client = TestClient(create_app(settings=settings))

    response = client.post(
        "/api/project-templates/starter/instantiate",
        json={
            "project_id": "custom-project",
            "name": "Custom Project",
            "description": "Fresh storyline.",
        },
    )

    assert response.status_code == 201

    payload = response.json()
    assert payload["data"]["id"] == "custom-project"
    assert payload["data"]["name"] == "Custom Project"
    assert payload["data"]["description"] == "Fresh storyline."
    assert payload["data"]["checksum"] == checksum
    assert payload["scenes"] == scenes

    created_dataset = project_root / "custom-project" / "template.json"
    metadata_path = project_root / "custom-project" / "project.json"

    with created_dataset.open("r", encoding="utf-8") as handle:
        stored_scenes = json.load(handle)

    with metadata_path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    assert stored_scenes == scenes
    assert metadata["name"] == "Custom Project"
    assert metadata["description"] == "Fresh storyline."
    assert metadata["scene_path"] == "template.json"

    project_response = client.get("/api/projects/custom-project")
    assert project_response.status_code == 200
    assert project_response.json()["scenes"] == scenes


def test_project_template_endpoints_return_404_when_disabled(tmp_path: Path) -> None:
    settings = SceneApiSettings(project_root=tmp_path / "projects")
    client = TestClient(create_app(settings=settings))

    response = client.get("/api/project-templates")
    assert response.status_code == 404

    instantiate_response = client.post(
        "/api/project-templates/starter/instantiate",
        json={"project_id": "example"},
    )
    assert instantiate_response.status_code == 404


def test_instantiate_project_template_rejects_invalid_identifier(
    tmp_path: Path,
) -> None:
    scenes: dict[str, Any] = {
        "intro": {
            "description": "Intro",
            "choices": [
                {"command": "go", "description": "Go"},
            ],
            "transitions": {"go": {"narration": "Go", "target": None}},
        }
    }

    template_root = tmp_path / "templates"
    project_root = tmp_path / "projects"

    _write_project(
        template_root,
        "starter",
        scenes,
        metadata={"name": "Starter"},
    )

    settings = SceneApiSettings(
        project_root=project_root, project_template_root=template_root
    )
    client = TestClient(create_app(settings=settings))

    response = client.post(
        "/api/project-templates/starter/instantiate",
        json={"project_id": "Invalid Identifier"},
    )

    assert response.status_code == 400
    assert "Project identifier" in response.json()["detail"]
