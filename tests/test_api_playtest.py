from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from textadventure.api.app import SceneProjectStore, create_app
from textadventure.api.settings import SceneApiSettings


def _create_project_dataset(root: Path, identifier: str) -> None:
    store = SceneProjectStore(root=root)
    scenes = {
        "starting-area": {
            "description": "Custom start location with a gentle breeze.",
            "choices": [
                {"command": "wait", "description": "Pause for a moment."},
            ],
            "transitions": {
                "wait": {"narration": "The breeze settles as time passes."}
            },
        }
    }
    store.create(identifier=identifier, scenes=scenes)


def test_playtest_websocket_basic_flow() -> None:
    app = create_app()
    client = TestClient(app)

    with client.websocket("/api/playtest") as session:
        initial = session.receive_json()
        assert initial["type"] == "event"
        assert "Sunlight filters" in initial["event"]["narration"]
        assert initial["world"]["location"] == "starting-area"
        assert initial["world"]["recent_actions"] == []

        session.send_json({"type": "player_input", "input": "explore"})
        follow_up = session.receive_json()
        assert follow_up["world"]["location"] == "old-gate"
        assert "courtyard" in follow_up["event"]["narration"].lower()


def test_playtest_websocket_reset_command() -> None:
    app = create_app()
    client = TestClient(app)

    with client.websocket("/api/playtest") as session:
        session.receive_json()
        session.send_json({"type": "player_input", "input": "explore"})
        session.receive_json()

        session.send_json({"type": "reset"})
        reset_message = session.receive_json()
        assert reset_message["world"]["location"] == "starting-area"
        assert reset_message["world"]["recent_actions"] == []


def test_playtest_websocket_configure_project(tmp_path: Path) -> None:
    _create_project_dataset(tmp_path, "custom")
    settings = SceneApiSettings(project_root=tmp_path)
    app = create_app(settings=settings)
    client = TestClient(app)

    with client.websocket("/api/playtest?project_id=custom") as session:
        initial = session.receive_json()
        assert (
            initial["event"]["narration"]
            == "Custom start location with a gentle breeze."
        )

        session.send_json({"type": "player_input", "input": "wait"})
        after_wait = session.receive_json()
        assert after_wait["world"]["location"] == "starting-area"
        assert after_wait["event"]["narration"] == "The breeze settles as time passes."

    with client.websocket("/api/playtest") as session:
        session.receive_json()
        session.send_json({"type": "configure", "project_id": "custom"})
        configured = session.receive_json()
        assert (
            configured["event"]["narration"]
            == "Custom start location with a gentle breeze."
        )


def test_playtest_websocket_reports_invalid_messages() -> None:
    app = create_app()
    client = TestClient(app)

    with client.websocket("/api/playtest") as session:
        session.receive_json()
        session.send_json({"unexpected": "value"})
        error = session.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "invalid-message"

        session.send_json({"type": "configure", "project_id": ""})
        error = session.receive_json()
        assert error["code"] == "invalid-project"
