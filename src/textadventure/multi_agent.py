"""Prototype components for coordinating multiple narrative agents."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable, Mapping, Protocol, Sequence
from types import MappingProxyType

from .memory import MemoryRequest
from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .world_state import WorldState


def _normalise_mapping(values: Mapping[str, str] | None) -> Mapping[str, str]:
    """Return an immutable mapping with stringified, stripped keys/values."""

    if not values:
        return MappingProxyType({})

    normalised: dict[str, str] = {}
    for key, value in values.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text:
            raise ValueError("metadata keys must be non-empty strings")
        if not value_text:
            raise ValueError("metadata values must be non-empty strings")
        normalised[key_text] = value_text
    return MappingProxyType(normalised)


@dataclass(frozen=True)
class AgentTrigger:
    """Context describing why an agent is being invoked."""

    kind: str
    player_input: str | None = None
    source_event: StoryEvent | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    memory_request: MemoryRequest | None = None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip()
        if not kind:
            raise ValueError("trigger kind must be a non-empty string")
        object.__setattr__(self, "kind", kind)

        if self.player_input is not None and not isinstance(self.player_input, str):
            raise TypeError(
                "player_input must be a string when provided",
            )

        object.__setattr__(self, "metadata", _normalise_mapping(self.metadata))

        if self.memory_request is not None and not isinstance(
            self.memory_request, MemoryRequest
        ):
            raise TypeError("memory_request must be a MemoryRequest or None")


@dataclass(frozen=True)
class AgentTurnResult:
    """Outcome produced by an agent for a single trigger."""

    event: StoryEvent | None = None
    messages: Sequence[AgentTrigger] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.event is not None and not isinstance(self.event, StoryEvent):
            raise TypeError("event must be a StoryEvent or None")
        object.__setattr__(self, "messages", tuple(self.messages))


@dataclass(frozen=True)
class QueuedAgentMessage:
    """Lightweight view of a queued message awaiting delivery."""

    origin_agent: str
    trigger_kind: str
    player_input: str | None
    metadata: Mapping[str, str]
    memory_request: MemoryRequest | None = None

    def __post_init__(self) -> None:
        origin = str(self.origin_agent).strip()
        if not origin:
            raise ValueError("origin_agent must be a non-empty string")
        object.__setattr__(self, "origin_agent", origin)

        kind = str(self.trigger_kind).strip()
        if not kind:
            raise ValueError("trigger_kind must be a non-empty string")
        object.__setattr__(self, "trigger_kind", kind)

        if self.player_input is not None and not isinstance(self.player_input, str):
            raise TypeError("player_input must be a string when provided")

        normalised: dict[str, str] = {}
        for key, value in (self.metadata or {}).items():
            key_text = str(key).strip()
            value_text = str(value).strip()
            if not key_text:
                raise ValueError("metadata keys must be non-empty strings")
            if not value_text:
                raise ValueError("metadata values must be non-empty strings")
            normalised[key_text] = value_text
        object.__setattr__(self, "metadata", MappingProxyType(normalised))

        if self.memory_request is not None and not isinstance(
            self.memory_request, MemoryRequest
        ):
            raise TypeError("memory_request must be a MemoryRequest or None")


@dataclass(frozen=True)
class CoordinatorDebugState:
    """Introspective snapshot of the coordinator for debugging."""

    queued_messages: Sequence[QueuedAgentMessage] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "queued_messages", tuple(self.queued_messages))


class Agent(Protocol):
    """Protocol describing participants managed by the coordinator."""

    name: str

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        """Respond to a trigger by producing an optional event and messages."""


class ScriptedStoryAgent(Agent):
    """Adapter that allows ``ScriptedStoryEngine`` to act as an agent."""

    def __init__(self, name: str, engine: StoryEngine) -> None:
        if not isinstance(name, str):
            raise TypeError("agent name must be a string")
        if not name.strip():
            raise ValueError("agent name must be a non-empty string")
        self.name = name.strip()
        self._engine = engine

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        if trigger.kind == "player-input":
            event = self._engine.propose_event(
                world_state,
                player_input=trigger.player_input,
            )
        else:
            event = self._engine.propose_event(world_state)
        return AgentTurnResult(event=event)


class MultiAgentCoordinator(StoryEngine):
    """Deterministic coordinator that merges outputs from multiple agents."""

    def __init__(
        self,
        primary_agent: Agent,
        *,
        secondary_agents: Sequence[Agent] | None = None,
    ) -> None:
        self._primary = primary_agent
        self._secondary_agents = tuple(secondary_agents or ())
        all_names = [primary_agent.name, *[agent.name for agent in self._secondary_agents]]
        if len(all_names) != len(set(all_names)):
            raise ValueError("agent names must be unique")
        self._is_first_turn = True
        self._agents_by_name = {primary_agent.name: primary_agent}
        for agent in self._secondary_agents:
            self._agents_by_name[agent.name] = agent
        self._queued_messages: Deque[_QueuedMessage] = deque()

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        accumulator = _EventAccumulator()
        next_turn_messages: list[_QueuedMessage] = []

        def queue_messages(agent_name: str, messages: Sequence[AgentTrigger]) -> None:
            for message in messages:
                next_turn_messages.append(
                    _QueuedMessage(origin_agent=agent_name, trigger=message)
                )

        def run_agent(
            agent: Agent,
            trigger: AgentTrigger,
            *,
            prefer_metadata_keys: bool = False,
        ) -> None:
            result = agent.propose_event(world_state, trigger=trigger)
            if result.event is not None:
                accumulator.add_event(
                    result.event,
                    agent_name=agent.name,
                    prefer_metadata_keys=prefer_metadata_keys,
                )
            queue_messages(agent.name, result.messages)

        for message in self._drain_message_queue():
            for recipient in self._resolve_recipients(message):
                run_agent(recipient, message.trigger)

        trigger_kind = "player-input" if player_input is not None else (
            "initial" if self._is_first_turn else "tick"
        )
        primary_trigger = AgentTrigger(
            kind=trigger_kind,
            player_input=player_input,
        )
        run_agent(
            self._primary,
            primary_trigger,
            prefer_metadata_keys=True,
        )
        if accumulator.is_empty:
            raise ValueError(
                "primary agent must always produce a StoryEvent",
            )

        follow_up_trigger = AgentTrigger(
            kind="story-event",
            player_input=player_input,
            source_event=accumulator.primary_event,
        )

        for agent in self._secondary_agents:
            run_agent(agent, follow_up_trigger)

        self._is_first_turn = False
        self._queued_messages.extend(next_turn_messages)
        return accumulator.build_event()

    def debug_snapshot(self) -> CoordinatorDebugState:
        """Return a snapshot describing the coordinator's queued messages."""

        messages = tuple(
            QueuedAgentMessage(
                origin_agent=message.origin_agent,
                trigger_kind=message.trigger.kind,
                player_input=message.trigger.player_input,
                metadata=dict(message.trigger.metadata),
                memory_request=message.trigger.memory_request,
            )
            for message in self._queued_messages
        )
        return CoordinatorDebugState(queued_messages=messages)

    def _iter_agents(self) -> Iterable[Agent]:
        yield self._primary
        yield from self._secondary_agents

    def _drain_message_queue(self) -> Sequence["_QueuedMessage"]:
        messages = tuple(self._queued_messages)
        self._queued_messages.clear()
        return messages

    def _resolve_recipients(self, message: "_QueuedMessage") -> Sequence[Agent]:
        trigger = message.trigger
        target_name = trigger.metadata.get("target") if trigger.metadata else None
        if target_name:
            try:
                return (self._agents_by_name[target_name],)
            except KeyError as exc:  # pragma: no cover - defensive branch
                raise ValueError(
                    f"queued message targeted unknown agent {target_name!r}",
                ) from exc

        return tuple(
            agent
            for agent in self._iter_agents()
            if agent.name != message.origin_agent
        )


class _EventAccumulator:
    """Helper for combining multiple ``StoryEvent`` instances."""

    def __init__(self) -> None:
        self._narrations: list[tuple[bool, str]] = []
        self._choices: dict[str, StoryChoice] = {}
        self._metadata: dict[str, str] = {}
        self._primary_event: StoryEvent | None = None

    def add_event(
        self,
        event: StoryEvent,
        *,
        agent_name: str,
        prefer_metadata_keys: bool = False,
    ) -> None:
        if event.narration:
            self._narrations.append((prefer_metadata_keys, event.narration))
            if self._primary_event is None and prefer_metadata_keys:
                self._primary_event = event

        for choice in event.choices:
            if choice.command not in self._choices:
                self._choices[choice.command] = choice

        for key, value in event.metadata.items():
            if prefer_metadata_keys and key not in self._metadata:
                self._metadata[key] = value
                continue

            namespaced_key = f"{agent_name}:{key}" if key in self._metadata or not prefer_metadata_keys else key
            self._metadata[namespaced_key] = value

    def build_event(self) -> StoryEvent:
        if not self._narrations:
            raise ValueError("no narration was provided by the coordinated agents")
        primary_segments = [text for is_primary, text in self._narrations if is_primary]
        other_segments = [text for is_primary, text in self._narrations if not is_primary]
        narration = "\n\n".join([*primary_segments, *other_segments])
        return StoryEvent(
            narration=narration,
            choices=tuple(self._choices.values()),
            metadata=dict(self._metadata) if self._metadata else None,
        )

    @property
    def is_empty(self) -> bool:
        return not self._narrations

    @property
    def primary_event(self) -> StoryEvent:
        if self._primary_event is None:
            raise ValueError("primary event has not been recorded")
        return self._primary_event


@dataclass(frozen=True)
class _QueuedMessage:
    origin_agent: str
    trigger: AgentTrigger


__all__ = [
    "Agent",
    "AgentTrigger",
    "AgentTurnResult",
    "CoordinatorDebugState",
    "MultiAgentCoordinator",
    "QueuedAgentMessage",
    "ScriptedStoryAgent",
]
