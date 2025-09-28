"""Lightweight memory utilities for tracking player actions and observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Sequence, Tuple


def _validate_limit(value: int | None, *, field_name: str) -> int | None:
    """Ensure optional numeric limits are non-negative integers."""

    if value is None:
        return None
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int or None, got {type(value)!r}")
    if value < 0:
        raise ValueError(f"{field_name} must be zero or a positive integer")
    return value


def _validate_text(value: str, *, field_name: str) -> str:
    """Normalise and validate free-form text fields."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")
    return stripped


@dataclass(frozen=True)
class MemoryEntry:
    """Represents a single memory captured by the adventure agent."""

    kind: str
    content: str
    tags: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MemoryRequest:
    """Describe how much recent memory should be surfaced to an agent."""

    action_limit: int | None = None
    observation_limit: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "action_limit",
            _validate_limit(self.action_limit, field_name="action_limit"),
        )
        object.__setattr__(
            self,
            "observation_limit",
            _validate_limit(self.observation_limit, field_name="observation_limit"),
        )

    def resolve_action_limit(self, default: int) -> int:
        """Return the requested action limit or fall back to ``default``."""

        return default if self.action_limit is None else self.action_limit

    def resolve_observation_limit(self, default: int) -> int:
        """Return the requested observation limit or fall back to ``default``."""

        return default if self.observation_limit is None else self.observation_limit


class MemoryLog:
    """Store and retrieve structured memories about the session."""

    def __init__(self) -> None:
        self._entries: List[MemoryEntry] = []

    def remember(
        self, kind: str, content: str, *, tags: Iterable[str] | None = None
    ) -> MemoryEntry:
        """Record a new memory and return the stored entry."""

        normalised_kind = _validate_text(kind, field_name="kind").lower()
        normalised_content = _validate_text(content, field_name="content")

        normalised_tags: Tuple[str, ...]
        if tags is None:
            normalised_tags = ()
        else:
            unique_tags: List[str] = []
            for tag in tags:
                validated = _validate_text(tag, field_name="tag").lower()
                if validated not in unique_tags:
                    unique_tags.append(validated)
            normalised_tags = tuple(unique_tags)

        entry = MemoryEntry(
            kind=normalised_kind,
            content=normalised_content,
            tags=normalised_tags,
        )
        self._entries.append(entry)
        return entry

    def recent(
        self, *, kind: str | None = None, limit: int | None = None
    ) -> Sequence[MemoryEntry]:
        """Return the most recent memories optionally filtered by ``kind``."""

        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative when provided")

        filtered = [
            entry
            for entry in self._entries
            if kind is None or entry.kind == kind.lower()
        ]
        if limit is None:
            return tuple(filtered)

        if limit == 0:
            return ()

        return tuple(filtered[-limit:])

    def find_by_tag(self, tag: str) -> Sequence[MemoryEntry]:
        """Return memories tagged with the provided keyword."""

        normalised_tag = _validate_text(tag, field_name="tag").lower()
        return tuple(entry for entry in self._entries if normalised_tag in entry.tags)

    def clear(self) -> None:
        """Remove all stored memories."""

        self._entries.clear()

    def __len__(self) -> int:  # pragma: no cover - trivial delegation
        return len(self._entries)

    def __iter__(self) -> Iterator[MemoryEntry]:  # pragma: no cover
        return iter(self._entries)


__all__ = ["MemoryEntry", "MemoryLog", "MemoryRequest"]
