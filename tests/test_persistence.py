import json
from pathlib import Path

import pytest

from textadventure import (
    FileSessionStore,
    InMemorySessionStore,
    SessionSnapshot,
    WorldState,
)


@pytest.fixture
def sample_snapshot() -> SessionSnapshot:
    return SessionSnapshot(
        world_state=WorldState(
            location="mysterious-cave",
            inventory={"torch", "map"},
            history=["Woke up.", "Picked up torch.", "Studied the map."],
        )
    )


def test_in_memory_session_store_round_trip(sample_snapshot: SessionSnapshot) -> None:
    store = InMemorySessionStore()
    store.save("session-1", sample_snapshot)

    retrieved = store.load("session-1")
    assert retrieved is sample_snapshot
    assert store.list_sessions() == ["session-1"]

    store.delete("session-1")
    assert store.list_sessions() == []
    with pytest.raises(KeyError):
        store.load("session-1")


def test_in_memory_session_store_validates_identifier(sample_snapshot: SessionSnapshot) -> None:
    store = InMemorySessionStore()
    with pytest.raises(ValueError):
        store.save("   ", sample_snapshot)
    with pytest.raises(TypeError):
        store.save(123, sample_snapshot)  # type: ignore[arg-type]


def test_file_session_store_round_trip(tmp_path: Path, sample_snapshot: SessionSnapshot) -> None:
    store = FileSessionStore(tmp_path)
    store.save("my-session", sample_snapshot)

    retrieved = store.load("my-session")
    assert retrieved.world_state.location == sample_snapshot.world_state.location
    assert retrieved.world_state.inventory == sample_snapshot.world_state.inventory
    assert retrieved.world_state.history == sample_snapshot.world_state.history

    listing_before_delete = store.list_sessions()
    assert listing_before_delete == ["my-session"]

    store.delete("my-session")
    assert store.list_sessions() == []
    with pytest.raises(KeyError):
        store.load("my-session")


def test_file_session_store_persists_json(tmp_path: Path, sample_snapshot: SessionSnapshot) -> None:
    store = FileSessionStore(tmp_path)
    store.save("persisted", sample_snapshot)

    payload = json.loads((tmp_path / "persisted.json").read_text(encoding="utf-8"))
    assert payload["world_state"]["location"] == "mysterious-cave"
    assert sorted(payload["world_state"]["inventory"]) == ["map", "torch"]
    assert payload["world_state"]["history"] == sample_snapshot.world_state.history


def test_snapshot_from_payload_validates() -> None:
    with pytest.raises(ValueError):
        SessionSnapshot.from_payload({})

    with pytest.raises(ValueError):
        SessionSnapshot.from_payload({"world_state": {"inventory": "not-iterable"}})

    with pytest.raises(ValueError):
        SessionSnapshot.from_payload({"world_state": {"history": "not-iterable"}})

    snapshot = SessionSnapshot.from_payload(
        {
            "world_state": {
                "location": "forest",
                "inventory": ["staff"],
                "history": ["Started."],
            }
        }
    )
    assert snapshot.world_state.location == "forest"
    assert snapshot.world_state.inventory == {"staff"}
    assert snapshot.world_state.history == ["Started."]
