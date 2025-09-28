import json
from pathlib import Path

import pytest

from textadventure import (
    FileSessionStore,
    InMemorySessionStore,
    MemoryLog,
    SessionSnapshot,
    WorldState,
)


@pytest.fixture
def sample_snapshot() -> SessionSnapshot:
    memory = MemoryLog()
    memory.remember("action", "wake up")
    memory.remember("observation", "It is dark.")

    return SessionSnapshot.capture(
        WorldState(
            location="mysterious-cave",
            inventory={"torch", "map"},
            history=["Woke up.", "Picked up torch.", "Studied the map."],
            memory=memory,
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


def test_in_memory_session_store_validates_identifier(
    sample_snapshot: SessionSnapshot,
) -> None:
    store = InMemorySessionStore()
    with pytest.raises(ValueError):
        store.save("   ", sample_snapshot)
    with pytest.raises(TypeError):
        store.save(123, sample_snapshot)  # type: ignore[arg-type]


def test_file_session_store_round_trip(
    tmp_path: Path, sample_snapshot: SessionSnapshot
) -> None:
    store = FileSessionStore(tmp_path)
    store.save("my-session", sample_snapshot)

    retrieved = store.load("my-session")
    assert retrieved.world_state.location == sample_snapshot.world_state.location
    assert retrieved.world_state.inventory == sample_snapshot.world_state.inventory
    assert retrieved.world_state.history == sample_snapshot.world_state.history
    assert (
        retrieved.world_state.memory.recent()
        == sample_snapshot.world_state.memory.recent()
    )

    listing_before_delete = store.list_sessions()
    assert listing_before_delete == ["my-session"]

    store.delete("my-session")
    assert store.list_sessions() == []
    with pytest.raises(KeyError):
        store.load("my-session")


def test_file_session_store_persists_json(
    tmp_path: Path, sample_snapshot: SessionSnapshot
) -> None:
    store = FileSessionStore(tmp_path)
    store.save("persisted", sample_snapshot)

    payload = json.loads((tmp_path / "persisted.json").read_text(encoding="utf-8"))
    assert payload["world_state"]["location"] == "mysterious-cave"
    assert sorted(payload["world_state"]["inventory"]) == ["map", "torch"]
    assert payload["world_state"]["history"] == sample_snapshot.world_state.history
    assert payload["world_state"]["memory"] == [
        {"kind": "action", "content": "wake up", "tags": []},
        {"kind": "observation", "content": "It is dark.", "tags": []},
    ]


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
                "memory": [
                    {"kind": "action", "content": "move", "tags": ["northern"]},
                ],
            }
        }
    )
    assert snapshot.world_state.location == "forest"
    assert snapshot.world_state.inventory == {"staff"}
    assert snapshot.world_state.history == ["Started."]
    assert [entry.kind for entry in snapshot.world_state.memory.recent()] == ["action"]
    assert [entry.content for entry in snapshot.world_state.memory.recent()] == ["move"]
    assert [entry.tags for entry in snapshot.world_state.memory.recent()] == [
        ("northern",)
    ]


def test_session_snapshot_apply_to_world(sample_snapshot: SessionSnapshot) -> None:
    world = WorldState(location="plaza")
    world.add_item("coin")
    world.record_event("Found fountain")

    sample_snapshot.apply_to_world(world)

    assert world.location == "mysterious-cave"
    assert world.inventory == {"torch", "map"}
    assert world.history == ["Woke up.", "Picked up torch.", "Studied the map."]
    assert [entry.kind for entry in world.memory.recent()] == [
        "action",
        "observation",
    ]
