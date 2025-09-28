"""Utility abstractions for tools that support the adventure framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported only for type checking
    from .world_state import WorldState


def _validate_text(value: str, *, field_name: str) -> str:
    """Ensure the provided value is a non-empty piece of text."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")

    return stripped


@dataclass(frozen=True)
class ToolResponse:
    """Structured response returned by a tool invocation."""

    narration: str
    metadata: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        narration = _validate_text(self.narration, field_name="narration")
        object.__setattr__(self, "narration", narration)

        if self.metadata is None:
            metadata: Mapping[str, str] = MappingProxyType({})
        else:
            metadata = MappingProxyType(
                {
                    _validate_text(str(key), field_name="metadata key"): _validate_text(
                        str(value), field_name="metadata value"
                    )
                    for key, value in self.metadata.items()
                }
            )
        object.__setattr__(self, "metadata", metadata)


class Tool(ABC):
    """Base class for utilities that the story engine can invoke."""

    def __init__(self, name: str, description: str) -> None:
        self._name = _validate_text(name, field_name="tool name")
        self._description = _validate_text(description, field_name="tool description")

    @property
    def name(self) -> str:
        """Human-readable identifier for the tool."""

        return self._name

    @property
    def description(self) -> str:
        """Summary of what the tool can do."""

        return self._description

    @abstractmethod
    def invoke(self, query: str, *, world_state: WorldState) -> ToolResponse:
        """Execute the tool with the provided query and world context."""

    def usage_hints(self) -> Sequence[str]:
        """Return optional usage hints for the tool."""

        return ()


class KnowledgeBaseTool(Tool):
    """Simple lookup tool backed by a static mapping of lore entries."""

    def __init__(
        self,
        entries: Mapping[str, str],
        *,
        name: str = "Field Guide",
        description: str = "Provides lore snippets about notable topics.",
    ) -> None:
        if not entries:
            raise ValueError("entries must contain at least one topic")

        super().__init__(name=name, description=description)

        normalised: dict[str, str] = {}
        for topic, text in entries.items():
            key = _validate_text(topic, field_name="topic name").lower()
            value = _validate_text(text, field_name="topic entry")
            if key in normalised:
                raise ValueError(f"duplicate topic provided: {topic!r}")
            normalised[key] = value

        self._entries: Mapping[str, str] = MappingProxyType(normalised)

    def available_topics(self) -> Sequence[str]:
        """Return the list of topics this knowledge base understands."""

        return tuple(sorted(self._entries.keys()))

    def usage_hints(self) -> Sequence[str]:  # pragma: no cover - trivial delegation
        topics = self.available_topics()
        if not topics:
            return ()
        return ("Try topics like: " + ", ".join(topics),)

    def invoke(self, query: str, *, world_state: WorldState) -> ToolResponse:
        del world_state  # The static knowledge base does not currently inspect it.

        cleaned_query = query.strip().lower()
        if not cleaned_query:
            hints = self.usage_hints()
            hint_text = "\n".join(hints) if hints else "Try specifying a topic name."
            return ToolResponse(
                narration=(
                    "You flip through the field guide but need a topic to look up.\n"
                    f"{hint_text}"
                ),
                metadata={"tool": self.name, "status": "missing_query"},
            )

        entry = self._entries.get(cleaned_query)
        if entry is None:
            hints = self.usage_hints()
            hint_text = (
                "\n".join(hints) if hints else "No additional topics are listed."
            )
            return ToolResponse(
                narration=(
                    f"The field guide has no entry for '{cleaned_query}'.\n{hint_text}"
                ),
                metadata={
                    "tool": self.name,
                    "status": "not_found",
                    "topic": cleaned_query,
                },
            )

        return ToolResponse(
            narration=entry,
            metadata={"tool": self.name, "status": "ok", "topic": cleaned_query},
        )


__all__ = ["KnowledgeBaseTool", "Tool", "ToolResponse"]
