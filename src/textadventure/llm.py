"""Abstractions for interacting with large language model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping, MutableMapping, Sequence


def _validate_text(value: str, *, field_name: str) -> str:
    """Ensure text fields contain non-empty string values."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string, got {type(value)!r}")

    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be a non-empty string")

    return stripped


@dataclass(frozen=True)
class LLMMessage:
    """Represents a single message exchanged with an LLM service."""

    role: str
    content: str

    def __post_init__(self) -> None:  # pragma: no cover - trivial setters
        role = _validate_text(self.role, field_name="role").lower()
        content = _validate_text(self.content, field_name="content")

        object.__setattr__(self, "role", role)
        object.__setattr__(self, "content", content)


@dataclass(frozen=True)
class LLMResponse:
    """Container describing the result returned by an LLM invocation."""

    message: LLMMessage
    usage: Mapping[str, int] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        usage_proxy = _frozen_int_mapping(self.usage, field_name="usage")
        metadata_proxy = _frozen_str_mapping(self.metadata, field_name="metadata")

        object.__setattr__(self, "usage", usage_proxy)
        object.__setattr__(self, "metadata", metadata_proxy)


def _frozen_int_mapping(
    mapping: Mapping[str, int] | MutableMapping[str, int], *, field_name: str
) -> Mapping[str, int]:
    """Validate that mapping values are integers and return an immutable view."""

    if mapping is None:
        data: Mapping[str, int] = {}
    else:
        data = {
            _validate_text(str(key), field_name=f"{field_name} key"): _validate_int(
                value, field_name=f"{field_name} value"
            )
            for key, value in mapping.items()
        }

    return MappingProxyType(dict(data))


def _validate_int(value: int, *, field_name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an int, got {type(value)!r}")
    return value


def _frozen_str_mapping(
    mapping: Mapping[str, str] | MutableMapping[str, str], *, field_name: str
) -> Mapping[str, str]:
    """Validate that mapping values are strings and return an immutable view."""

    if mapping is None:
        data: Mapping[str, str] = {}
    else:
        data = {
            _validate_text(str(key), field_name=f"{field_name} key"): _validate_text(
                str(value), field_name=f"{field_name} value"
            )
            for key, value in mapping.items()
        }

    return MappingProxyType(dict(data))


class LLMClient(ABC):
    """Abstract interface encapsulating calls to an LLM provider."""

    @abstractmethod
    def complete(
        self, messages: Sequence[LLMMessage], *, temperature: float | None = None
    ) -> LLMResponse:
        """Generate a completion from a set of chat-style messages."""

    def complete_prompt(
        self, prompt: str, *, temperature: float | None = None
    ) -> LLMResponse:
        """Helper for providers that accept a single user prompt."""

        message = LLMMessage(role="user", content=prompt)
        return self.complete([message], temperature=temperature)


class LLMClientError(RuntimeError):
    """Base exception raised when the LLM client encounters a failure."""


def iter_contents(messages: Iterable[LLMMessage]) -> Sequence[str]:
    """Extract just the textual payloads from a collection of messages."""

    return [message.content for message in messages]


__all__ = [
    "LLMClient",
    "LLMClientError",
    "LLMMessage",
    "LLMResponse",
    "iter_contents",
]
