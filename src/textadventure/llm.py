"""Abstractions for interacting with large language model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Iterable,
    Mapping,
    MutableMapping,
    Protocol,
    Sequence,
    TypeVar,
)

import random
import time


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


@dataclass(frozen=True)
class LLMCapability:
    """Describes whether a capability is supported and optional metadata about it."""

    supported: bool
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.supported, bool):
            raise TypeError(f"supported must be a bool, got {type(self.supported)!r}")
        metadata_proxy = _frozen_str_mapping(self.metadata, field_name="metadata")
        object.__setattr__(self, "metadata", metadata_proxy)


@dataclass(frozen=True)
class LLMToolDescription:
    """Structured description of a tool interface exposed by an LLM provider."""

    name: str
    description: str | None = None
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = _validate_text(self.name, field_name="name")
        if self.description is not None:
            description = _validate_text(self.description, field_name="description")
        else:
            description = None

        schema_proxy = _frozen_generic_mapping(
            self.parameters_schema, field_name="parameters_schema"
        )

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "parameters_schema", schema_proxy)


@dataclass(frozen=True)
class LLMCapabilities:
    """Collection of high-level capabilities provided by an LLM integration."""

    streaming: LLMCapability = field(
        default_factory=lambda: LLMCapability(supported=False)
    )
    function_calling: LLMCapability = field(
        default_factory=lambda: LLMCapability(supported=False)
    )
    tools: Mapping[str, LLMToolDescription] = field(default_factory=dict)

    def __post_init__(self) -> None:
        tools_proxy = _frozen_tool_mapping(self.tools, field_name="tools")
        object.__setattr__(self, "tools", tools_proxy)

    def supports_streaming(self) -> bool:
        """Return ``True`` when the provider offers streaming responses."""

        return self.streaming.supported

    def supports_function_calling(self) -> bool:
        """Return ``True`` when structured function calling is available."""

        return self.function_calling.supported

    def has_tools(self) -> bool:
        """Return ``True`` when the provider exposes tool invocation APIs."""

        return bool(self.tools)

    def describe_tool(self, name: str) -> LLMToolDescription | None:
        """Return the tool description if ``name`` is registered."""

        key = _validate_text(name, field_name="tool name").lower()
        return self.tools.get(key)


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


def _frozen_generic_mapping(
    mapping: Mapping[str, Any] | MutableMapping[str, Any], *, field_name: str
) -> Mapping[str, Any]:
    """Validate keys are strings and return an immutable view."""

    if mapping is None:
        data: Mapping[str, Any] = {}
    else:
        data = {
            _validate_text(str(key), field_name=f"{field_name} key"): value
            for key, value in mapping.items()
        }

    return MappingProxyType(dict(data))


def _frozen_tool_mapping(
    mapping: Mapping[str, LLMToolDescription] | MutableMapping[str, LLMToolDescription],
    *,
    field_name: str,
) -> Mapping[str, LLMToolDescription]:
    """Normalise tool keys and return an immutable mapping."""

    if mapping is None:
        data: Mapping[str, LLMToolDescription] = {}
    else:
        data = {}
        for key, value in mapping.items():
            if not isinstance(value, LLMToolDescription):
                raise TypeError(
                    f"{field_name} values must be LLMToolDescription instances, got {type(value)!r}"
                )
            normalised_key = (
                _validate_text(str(key), field_name=f"{field_name} key").strip().lower()
            )
            data[normalised_key] = value

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

    def capabilities(self) -> LLMCapabilities:
        """Return metadata describing optional provider capabilities."""

        return LLMCapabilities()


class LLMClientError(RuntimeError):
    """Base exception raised when the LLM client encounters a failure."""


class LLMErrorCategory(str, Enum):
    """High-level categories used to classify LLM failures."""

    TRANSIENT = "transient"
    RATE_LIMIT = "rate_limit"
    FATAL = "fatal"

    def is_retryable(self) -> bool:
        """Return ``True`` when the category should trigger a retry."""

        return self in {self.TRANSIENT, self.RATE_LIMIT}


class LLMErrorClassifier:
    """Utility for mapping exceptions to :class:`LLMErrorCategory` values."""

    def __init__(
        self,
        *,
        default_category: LLMErrorCategory = LLMErrorCategory.FATAL,
        rules: Sequence[tuple[LLMErrorCategory, type[Exception]]] | None = None,
    ) -> None:
        self._default_category = default_category
        self._rules: list[tuple[type[Exception], LLMErrorCategory]] = []

        if rules is not None:
            for category, exc_type in rules:
                self.register(category, exc_type)

    def register(
        self, category: LLMErrorCategory, *exception_types: type[Exception]
    ) -> None:
        """Register one or more exception types for ``category``."""

        if not exception_types:
            raise ValueError("at least one exception type must be provided")

        for exc_type in exception_types:
            if not isinstance(exc_type, type) or not issubclass(exc_type, Exception):
                raise TypeError(
                    "exception_types must be Exception subclasses, " f"got {exc_type!r}"
                )
            self._rules.append((exc_type, category))

    def classify(self, error: Exception) -> LLMErrorCategory:
        """Return the category associated with ``error``."""

        for exc_type, category in self._rules:
            if isinstance(error, exc_type):
                return category
        return self._default_category


SleepFunction = Callable[[float], None]


class RateLimiter(Protocol):
    """Protocol describing the minimal rate limiter interface used by retries."""

    def acquire(self) -> None:
        """Block until an action is permitted."""


class FixedIntervalRateLimiter:
    """Enforce a minimum delay between successive operations."""

    def __init__(
        self,
        *,
        min_interval: float,
        clock: Callable[[], float] | None = None,
        sleep: SleepFunction | None = None,
    ) -> None:
        if min_interval < 0:
            raise ValueError("min_interval must be non-negative")

        self._min_interval = float(min_interval)
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._next_allowed = self._clock()

    def acquire(self) -> None:
        now = self._clock()
        wait_time = self._next_allowed - now
        if wait_time > 0:
            self._sleep(wait_time)
            now = self._clock()

        self._next_allowed = max(now, self._next_allowed) + self._min_interval


T = TypeVar("T")


@dataclass(frozen=True)
class LLMRetryPolicy:
    """Configuration controlling retry behaviour for LLM calls."""

    max_attempts: int = 3
    initial_backoff: float = 0.5
    backoff_multiplier: float = 2.0
    max_backoff: float = 30.0
    jitter: float = 0.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_backoff < 0:
            raise ValueError("initial_backoff must be non-negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")
        if self.max_backoff < 0:
            raise ValueError("max_backoff must be non-negative")
        if self.jitter < 0:
            raise ValueError("jitter must be non-negative")

    def compute_backoff(
        self, attempt: int, *, random_func: Callable[[], float] | None = None
    ) -> float:
        """Return the backoff delay for ``attempt`` (1-indexed)."""

        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        base_delay = self.initial_backoff * (self.backoff_multiplier ** (attempt - 1))
        delay = min(base_delay, self.max_backoff)

        if self.jitter <= 0 or delay == 0:
            return delay

        rng = random_func or random.random
        offset = (rng() * 2 - 1) * (delay * self.jitter)
        return max(0.0, delay + offset)


def call_with_retries(
    operation: Callable[[], T],
    *,
    retry_policy: LLMRetryPolicy | None = None,
    classifier: LLMErrorClassifier | None = None,
    rate_limiter: RateLimiter | None = None,
    sleep: SleepFunction | None = None,
    random_func: Callable[[], float] | None = None,
) -> T:
    """Execute ``operation`` with retry, backoff, and rate limiting support."""

    policy = retry_policy or LLMRetryPolicy()
    error_classifier = classifier or LLMErrorClassifier()
    sleep_fn = sleep or time.sleep

    attempt = 1
    while True:
        if rate_limiter is not None:
            rate_limiter.acquire()

        try:
            return operation()
        except Exception as error:
            category = error_classifier.classify(error)
            if not category.is_retryable() or attempt >= policy.max_attempts:
                raise

            delay = policy.compute_backoff(attempt, random_func=random_func)
            if delay > 0:
                sleep_fn(delay)

            attempt += 1


def iter_contents(messages: Iterable[LLMMessage]) -> Sequence[str]:
    """Extract just the textual payloads from a collection of messages."""

    return [message.content for message in messages]


__all__ = [
    "LLMClient",
    "LLMClientError",
    "LLMCapabilities",
    "LLMCapability",
    "LLMErrorCategory",
    "LLMErrorClassifier",
    "LLMMessage",
    "LLMToolDescription",
    "LLMResponse",
    "LLMRetryPolicy",
    "RateLimiter",
    "FixedIntervalRateLimiter",
    "call_with_retries",
    "iter_contents",
]
