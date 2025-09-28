"""Session persistence utilities for the text adventure framework."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from .memory import MemoryLog
from .world_state import WorldState


@dataclass
class SessionSnapshot:
    """Represents the data required to persist a single game session."""

    world_state: WorldState

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serialisable representation of the snapshot."""

        return {
            "world_state": {
                "location": self.world_state.location,
                "inventory": sorted(self.world_state.inventory),
                "history": list(self.world_state.history),
                "memory": [
                    {
                        "kind": entry.kind,
                        "content": entry.content,
                        "tags": list(entry.tags),
                    }
                    for entry in self.world_state.memory
                ],
            }
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, object]) -> "SessionSnapshot":
        """Build a snapshot from the stored payload representation."""

        world_state_payload = payload.get("world_state")
        if not isinstance(world_state_payload, dict):
            raise ValueError("Invalid snapshot payload: missing world_state")

        location = world_state_payload.get("location")
        inventory = world_state_payload.get("inventory", [])
        history = world_state_payload.get("history", [])

        if not isinstance(inventory, Iterable) or isinstance(inventory, (str, bytes)):
            raise ValueError("Invalid snapshot payload: inventory must be iterable")
        if not isinstance(history, Iterable) or isinstance(history, (str, bytes)):
            raise ValueError("Invalid snapshot payload: history must be iterable")

        memory = _memory_from_payload(world_state_payload.get("memory", []))

        return cls(
            world_state=WorldState(
                location=str(location) if location is not None else "starting-area",
                inventory=set(str(item) for item in inventory),
                history=[str(event) for event in history],
                memory=memory,
            )
        )

    @classmethod
    def capture(cls, world_state: WorldState) -> "SessionSnapshot":
        """Create a snapshot from the provided world state."""

        return cls(world_state=_clone_world_state(world_state))

    def apply_to_world(self, world_state: WorldState) -> None:
        """Mutate ``world_state`` to match this snapshot."""

        world_state.location = self.world_state.location
        world_state.inventory = set(self.world_state.inventory)
        world_state.history = list(self.world_state.history)
        world_state.memory = _clone_memory(self.world_state.memory)


class SessionStore(ABC):
    """Interface describing how session snapshots are persisted."""

    @abstractmethod
    def save(self, session_id: str, snapshot: SessionSnapshot) -> None:
        """Persist the snapshot for later retrieval."""

    @abstractmethod
    def load(self, session_id: str) -> SessionSnapshot:
        """Return the snapshot for the given session.

        Raises:
            KeyError: If the session cannot be found.
        """

    @abstractmethod
    def delete(self, session_id: str) -> None:
        """Remove the stored snapshot if it exists."""

    @abstractmethod
    def list_sessions(self) -> List[str]:
        """Return all session identifiers stored in this persistence layer."""


class InMemorySessionStore(SessionStore):
    """Keep session snapshots in local process memory."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionSnapshot] = {}

    def save(self, session_id: str, snapshot: SessionSnapshot) -> None:
        self._sessions[_validate_session_id(session_id)] = snapshot

    def load(self, session_id: str) -> SessionSnapshot:
        key = _validate_session_id(session_id)
        try:
            return self._sessions[key]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise KeyError(f"Session '{session_id}' does not exist") from exc

    def delete(self, session_id: str) -> None:
        key = _validate_session_id(session_id)
        self._sessions.pop(key, None)

    def list_sessions(self) -> List[str]:
        return sorted(self._sessions.keys())


class FileSessionStore(SessionStore):
    """Persist session snapshots as JSON files on disk."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, snapshot: SessionSnapshot) -> None:
        session_file = self._session_path(session_id)
        session_file.write_text(
            json.dumps(snapshot.to_payload(), indent=2), encoding="utf-8"
        )

    def load(self, session_id: str) -> SessionSnapshot:
        session_file = self._session_path(session_id)
        if not session_file.exists():
            raise KeyError(f"Session '{session_id}' does not exist")
        payload = json.loads(session_file.read_text(encoding="utf-8"))
        return SessionSnapshot.from_payload(payload)

    def delete(self, session_id: str) -> None:
        session_file = self._session_path(session_id)
        if session_file.exists():
            session_file.unlink()

    def list_sessions(self) -> List[str]:
        return sorted(
            session_path.stem
            for session_path in self.storage_dir.glob("*.json")
            if session_path.is_file()
        )

    def _session_path(self, session_id: str) -> Path:
        validated = _validate_session_id(session_id)
        return self.storage_dir / f"{validated}.json"


def _validate_session_id(session_id: str) -> str:
    if not isinstance(session_id, str):
        raise TypeError("session_id must be a string")
    stripped = session_id.strip()
    if not stripped:
        raise ValueError("session_id must be a non-empty string")
    return stripped


def _clone_world_state(world_state: WorldState) -> WorldState:
    return WorldState(
        location=world_state.location,
        inventory=set(world_state.inventory),
        history=list(world_state.history),
        memory=_clone_memory(world_state.memory),
    )


def _clone_memory(memory: MemoryLog) -> MemoryLog:
    clone = MemoryLog()
    for entry in memory:
        clone.remember(entry.kind, entry.content, tags=entry.tags)
    return clone


def _memory_from_payload(payload: object) -> MemoryLog:
    if isinstance(payload, (str, bytes)):
        raise ValueError("Invalid snapshot payload: memory must be a sequence")
    if payload is None:
        return MemoryLog()
    if not isinstance(payload, Iterable):
        raise ValueError("Invalid snapshot payload: memory must be iterable")

    log = MemoryLog()
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Invalid snapshot payload: memory entries must be objects")

        kind = entry.get("kind")
        content = entry.get("content")
        if kind is None or content is None:
            raise ValueError("Memory entry must include 'kind' and 'content'")

        tags_value = entry.get("tags", [])
        if isinstance(tags_value, (str, bytes)):
            raise ValueError("Memory entry tags must be a sequence")
        if not isinstance(tags_value, Iterable):
            raise ValueError("Memory entry tags must be iterable")

        tags: Sequence[str] = [str(tag) for tag in tags_value]
        log.remember(str(kind), str(content), tags=tags)
    return log
