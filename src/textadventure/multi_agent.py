"""Prototype components for coordinating multiple narrative agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence
from types import MappingProxyType

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


@dataclass(frozen=True)
class AgentTurnResult:
    """Outcome produced by an agent for a single trigger."""

    event: StoryEvent | None = None
    messages: Sequence[AgentTrigger] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.event is not None and not isinstance(self.event, StoryEvent):
            raise TypeError("event must be a StoryEvent or None")
        object.__setattr__(self, "messages", tuple(self.messages))


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

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        trigger_kind = "player-input" if player_input is not None else (
            "initial" if self._is_first_turn else "tick"
        )
        primary_trigger = AgentTrigger(
            kind=trigger_kind,
            player_input=player_input,
        )
        primary_result = self._primary.propose_event(
            world_state,
            trigger=primary_trigger,
        )
        if primary_result.event is None:
            raise ValueError(
                "primary agent must always produce a StoryEvent",
            )

        accumulator = _EventAccumulator()
        accumulator.add_event(primary_result.event, agent_name=self._primary.name, prefer_metadata_keys=True)

        follow_up_trigger = AgentTrigger(
            kind="story-event",
            player_input=player_input,
            source_event=primary_result.event,
        )

        for agent in self._secondary_agents:
            result = agent.propose_event(world_state, trigger=follow_up_trigger)
            if result.event is not None:
                accumulator.add_event(result.event, agent_name=agent.name)

        self._is_first_turn = False
        return accumulator.build_event()


class _EventAccumulator:
    """Helper for combining multiple ``StoryEvent`` instances."""

    def __init__(self) -> None:
        self._narrations: list[str] = []
        self._choices: dict[str, StoryChoice] = {}
        self._metadata: dict[str, str] = {}

    def add_event(
        self,
        event: StoryEvent,
        *,
        agent_name: str,
        prefer_metadata_keys: bool = False,
    ) -> None:
        if event.narration:
            self._narrations.append(event.narration)

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
        narration = "\n\n".join(self._narrations)
        return StoryEvent(
            narration=narration,
            choices=tuple(self._choices.values()),
            metadata=dict(self._metadata) if self._metadata else None,
        )


__all__ = [
    "Agent",
    "AgentTrigger",
    "AgentTurnResult",
    "MultiAgentCoordinator",
    "ScriptedStoryAgent",
]
