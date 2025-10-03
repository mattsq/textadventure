"""Interfaces for proposing narrative events within the adventure."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from .world_state import WorldState

from .markdown import render_markdown


def _validate_text(value: str, *, field_name: str) -> str:
    """Validate and normalise free-form text fields used by story elements."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")

    return stripped


@dataclass(frozen=True)
class StoryChoice:
    """Represents a single actionable option offered to the player."""

    command: str
    description: str

    def __post_init__(self) -> None:
        command = _validate_text(self.command, field_name="command").lower()
        description = _validate_text(self.description, field_name="choice description")

        object.__setattr__(self, "command", command)
        object.__setattr__(self, "description", description)


@dataclass(frozen=True)
class StoryEvent:
    """Encapsulates the narrative response produced by a story engine."""

    narration: str
    choices: Sequence[StoryChoice] = field(default_factory=tuple)
    metadata: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        narration = _validate_text(self.narration, field_name="narration")
        object.__setattr__(self, "narration", narration)

        normalised_choices = tuple(self.choices)
        seen_commands: set[str] = set()
        for choice in normalised_choices:
            if choice.command in seen_commands:
                raise ValueError(f"duplicate choice command: {choice.command}")
            seen_commands.add(choice.command)

        object.__setattr__(self, "choices", normalised_choices)

        metadata: Mapping[str, str]
        if self.metadata is None:
            metadata = MappingProxyType({})
        else:
            metadata = MappingProxyType(
                {
                    _validate_text(str(k), field_name="metadata key"): _validate_text(
                        str(v), field_name="metadata value"
                    )
                    for k, v in self.metadata.items()
                }
            )
        object.__setattr__(self, "metadata", metadata)

    @property
    def has_choices(self) -> bool:
        """Return ``True`` when the event offers at least one choice."""

        return bool(self.choices)

    def iter_choice_commands(self) -> Tuple[str, ...]:
        """Return the available commands as a tuple for quick lookups."""

        return tuple(choice.command for choice in self.choices)


class StoryEngine(ABC):
    """Abstract interface for components that drive narrative progression."""

    @abstractmethod
    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        """Produce the next story event based on the current context."""

    def format_event(self, event: StoryEvent) -> str:
        """Create a printable representation of a story event."""

        lines = [render_markdown(event.narration)]
        if event.choices:
            lines.append("")
            for choice in event.choices:
                description = render_markdown(choice.description)
                lines.append(f"[{choice.command}] {description}")
        return "\n".join(lines)


__all__ = ["StoryChoice", "StoryEvent", "StoryEngine"]
