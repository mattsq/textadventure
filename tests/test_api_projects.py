import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fastapi.testclient import TestClient

from textadventure.api import SceneApiSettings, create_app


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
        metadata={"name": "Editable"},
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/editable/collaborators",
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
        metadata={"name": "Solo"},
    )

    settings = SceneApiSettings(project_root=tmp_path)
    client = TestClient(create_app(settings=settings))

    response = client.put(
        "/api/projects/solo/collaborators",
        json={"collaborators": [{"user_id": "viewer@example.com", "role": "viewer"}]},
    )

    assert response.status_code == 400
    assert "owner" in response.json()["detail"]

    metadata_path = tmp_path / "solo" / "project.json"
    if metadata_path.exists():
        with metadata_path.open("r", encoding="utf-8") as handle:
            metadata = json.load(handle)
        assert "collaborators" not in metadata


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
