from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
import pytest

from textadventure.api import SceneApiSettings, create_app
from textadventure.api.app import CURRENT_SCENE_SCHEMA_VERSION


@pytest.fixture()
def marketplace_client(tmp_path: Path) -> TestClient:
    settings = SceneApiSettings(marketplace_root=tmp_path / "marketplace")
    return TestClient(create_app(settings=settings))


def _sample_scenes() -> dict[str, Any]:
    return {
        "start": {
            "description": "A quiet clearing",
            "choices": [
                {"command": "wait", "description": "Pause for a moment."},
                {"command": "walk", "description": "Follow the forest path."},
            ],
            "transitions": {
                "wait": {
                    "narration": "Time drifts by without incident.",
                    "target": None,
                },
                "walk": {
                    "narration": "You head deeper into the woods.",
                    "target": "trail",
                },
            },
        },
        "trail": {
            "description": "A winding woodland trail",
            "choices": [
                {"command": "return", "description": "Head back to the clearing."},
            ],
            "transitions": {
                "return": {
                    "narration": "You retrace your steps to the clearing.",
                    "target": "start",
                },
            },
        },
    }


def test_publish_marketplace_entry_and_retrieve(marketplace_client: TestClient) -> None:
    scenes = _sample_scenes()
    payload = {
        "title": "Hidden Grotto",
        "description": "Short detour into a tranquil forest.",
        "author": "Aster",
        "tags": ["Mystery", " exploration "],
        "scenes": scenes,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    create_response = marketplace_client.post(
        "/api/marketplace/entries",
        json=payload,
    )
    assert create_response.status_code == 201

    created = create_response.json()
    assert created["id"] == "hidden-grotto"
    assert created["title"] == "Hidden Grotto"
    assert created["description"] == "Short detour into a tranquil forest."
    assert created["author"] == "Aster"
    assert created["tags"] == ["mystery", "exploration"]
    assert created["scene_count"] == len(scenes)
    assert created["schema_version"] == CURRENT_SCENE_SCHEMA_VERSION
    assert created["scenes"] == scenes

    list_response = marketplace_client.get("/api/marketplace/entries")
    assert list_response.status_code == 200

    listing = list_response.json()
    assert listing["pagination"]["total_items"] == 1
    assert listing["data"][0]["id"] == "hidden-grotto"
    assert listing["data"][0]["tags"] == ["mystery", "exploration"]

    detail_response = marketplace_client.get(
        f"/api/marketplace/entries/{created['id']}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["scenes"] == scenes


def test_publish_marketplace_entry_conflict_when_identifier_exists(
    marketplace_client: TestClient,
) -> None:
    scenes = _sample_scenes()
    body = {
        "identifier": "shared-demo",
        "title": "Shared Demo",
        "scenes": scenes,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    first_response = marketplace_client.post(
        "/api/marketplace/entries",
        json=body,
    )
    assert first_response.status_code == 201

    conflict_response = marketplace_client.post(
        "/api/marketplace/entries",
        json=body,
    )
    assert conflict_response.status_code == 409
    assert "already exists" in conflict_response.json()["detail"].lower()


def test_list_marketplace_entries_supports_filters(
    marketplace_client: TestClient,
) -> None:
    scenes = _sample_scenes()

    first_payload = {
        "title": "Arcane Tower",
        "tags": ["Magic", "Lore"],
        "scenes": scenes,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }
    second_payload = {
        "title": "Sunken Ruins",
        "tags": ["mystery"],
        "scenes": scenes,
        "schema_version": CURRENT_SCENE_SCHEMA_VERSION,
    }

    first_response = marketplace_client.post(
        "/api/marketplace/entries",
        json=first_payload,
    )
    assert first_response.status_code == 201

    second_response = marketplace_client.post(
        "/api/marketplace/entries",
        json=second_payload,
    )
    assert second_response.status_code == 201

    tag_filtered = marketplace_client.get(
        "/api/marketplace/entries", params={"tag": "magic"}
    )
    assert tag_filtered.status_code == 200
    tag_payload = tag_filtered.json()
    assert tag_payload["pagination"]["total_items"] == 1
    assert tag_payload["data"][0]["title"] == "Arcane Tower"

    search_filtered = marketplace_client.get(
        "/api/marketplace/entries", params={"search": "sunken"}
    )
    assert search_filtered.status_code == 200
    search_payload = search_filtered.json()
    assert search_payload["pagination"]["total_items"] == 1
    assert search_payload["data"][0]["title"] == "Sunken Ruins"

    empty_filtered = marketplace_client.get(
        "/api/marketplace/entries",
        params={"search": "sunken", "tag": "lore"},
    )
    assert empty_filtered.status_code == 200
    assert empty_filtered.json()["data"] == []
