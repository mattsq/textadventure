from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

from textadventure.api.app import (
    PlaytestSession,
    SceneProjectStore,
    create_app,
)
from textadventure.api.settings import SceneApiSettings
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_mapping,
)


def _build_simple_engine_factory() -> Callable[[], ScriptedStoryEngine]:
    definitions = {
        "starting-area": {
            "description": "A quiet clearing.",
            "choices": [
                {"command": "wait", "description": "Pause and listen."},
            ],
            "transitions": {
                "wait": {
                    "narration": "Time drifts by while the forest hums softly.",
                    "target": "starting-area",
                }
            },
        }
    }

    def _factory() -> ScriptedStoryEngine:
        scenes = load_scenes_from_mapping(definitions)
        return ScriptedStoryEngine(scenes=scenes)

    return _factory


def test_playtest_session_records_transcript_entries() -> None:
    session = PlaytestSession(_build_simple_engine_factory())

    initial_event = session.reset()
    entries = session.transcript()
    assert len(entries) == 1
    assert entries[0].player_input is None
    assert entries[0].event is initial_event

    follow_up = session.apply_player_input("wait")
    entries = session.transcript()
    assert len(entries) == 2
    assert entries[1].player_input == "wait"
    assert entries[1].event is follow_up
    assert "forest hums" in entries[1].event.narration


def test_playtest_session_resets_transcript_between_runs() -> None:
    session = PlaytestSession(_build_simple_engine_factory())

    session.reset()
    session.apply_player_input("wait")
    assert len(session.transcript()) == 2

    session.reset()
    entries = session.transcript()
    assert len(entries) == 1
    assert entries[0].turn == 1
    assert entries[0].player_input is None


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
