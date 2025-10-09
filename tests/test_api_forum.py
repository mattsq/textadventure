import pytest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from textadventure.api import SceneApiSettings, create_app


@pytest.fixture()
def forum_client(tmp_path: Path) -> TestClient:
    settings = SceneApiSettings(forum_root=tmp_path / "forums")
    return TestClient(create_app(settings=settings))


def test_create_forum_thread_and_list(forum_client: TestClient) -> None:
    create_response = forum_client.post(
        "/api/forums/threads",
        json={
            "title": "Design Feedback",
            "body": "Share your latest encounter ideas here.",
            "author": "Nova",
        },
    )
    assert create_response.status_code == 201

    created = create_response.json()
    assert created["title"] == "Design Feedback"
    assert created["author"] == "Nova"
    assert created["post_count"] == 1
    assert len(created["posts"]) == 1
    assert created["posts"][0]["body"] == "Share your latest encounter ideas here."

    list_response = forum_client.get("/api/forums/threads")
    assert list_response.status_code == 200

    listing = list_response.json()
    assert listing["pagination"]["total_items"] == 1
    assert listing["data"][0]["id"] == created["id"]
    assert listing["data"][0]["post_count"] == 1

    detail_response = forum_client.get(f"/api/forums/threads/{created['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["post_count"] == 1
    assert detail["posts"][0]["body"] == "Share your latest encounter ideas here."


def test_create_forum_thread_conflict_when_identifier_exists(
    forum_client: TestClient,
) -> None:
    payload: dict[str, Any] = {
        "identifier": "community-updates",
        "title": "Community Updates",
        "body": "Welcome to the forums!",
    }

    first_response = forum_client.post("/api/forums/threads", json=payload)
    assert first_response.status_code == 201

    conflict_response = forum_client.post("/api/forums/threads", json=payload)
    assert conflict_response.status_code == 409
    assert "already exists" in conflict_response.json()["detail"].lower()


def test_add_post_to_forum_thread(forum_client: TestClient) -> None:
    create_response = forum_client.post(
        "/api/forums/threads",
        json={
            "title": "Plot Twists",
            "body": "Kick off the discussion with your best twist.",
            "author": "Rowan",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()

    post_response = forum_client.post(
        f"/api/forums/threads/{created['id']}/posts",
        json={
            "body": "Consider foreshadowing with recurring motifs.",
            "author": "Quinn",
        },
    )
    assert post_response.status_code == 201

    detail_response = forum_client.get(f"/api/forums/threads/{created['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["post_count"] == 2
    assert [post["body"] for post in detail["posts"]] == [
        "Kick off the discussion with your best twist.",
        "Consider foreshadowing with recurring motifs.",
    ]
