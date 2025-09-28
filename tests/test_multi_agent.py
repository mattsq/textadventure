"""Tests for the multi-agent coordinator prototype."""

from __future__ import annotations

from typing import Sequence

import pytest

from textadventure.multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    MultiAgentCoordinator,
    QueuedAgentMessage,
    ScriptedStoryAgent,
)
from textadventure.memory import MemoryRequest
from textadventure.scripted_story_engine import ScriptedStoryEngine
from textadventure.story_engine import StoryChoice, StoryEvent
from textadventure.world_state import WorldState


class StubAgent(Agent):
    """Simple agent used to verify coordinator interactions."""

    def __init__(
        self,
        name: str,
        *,
        narration: str,
        choices: tuple[StoryChoice, ...] = (),
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._narration = narration
        self._choices = choices
        self._metadata = metadata or {}
        self.triggers: list[AgentTrigger] = []

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        del world_state
        self.triggers.append(trigger)
        return AgentTurnResult(
            event=StoryEvent(
                narration=self._narration,
                choices=self._choices,
                metadata=self._metadata,
            )
        )


class SequencedAgent(Agent):
    """Agent that replays a scripted sequence of turn results."""

    def __init__(self, name: str, results: Sequence[AgentTurnResult]) -> None:
        self.name = name
        self._results = list(results)
        self.triggers: list[AgentTrigger] = []

    def propose_event(
        self,
        world_state: WorldState,
        *,
        trigger: AgentTrigger,
    ) -> AgentTurnResult:
        del world_state
        self.triggers.append(trigger)
        if not self._results:
            raise AssertionError(f"no scripted result available for agent {self.name!r}")
        return self._results.pop(0)


def test_coordinator_defaults_to_primary_agent_output() -> None:
    """With only a primary agent, the coordinator mirrors its responses."""

    world = WorldState()
    scripted_engine = ScriptedStoryEngine()
    coordinator = MultiAgentCoordinator(
        ScriptedStoryAgent("narrator", scripted_engine)
    )

    expected = scripted_engine.propose_event(WorldState())
    result = coordinator.propose_event(world)

    assert result.narration == expected.narration
    assert result.choices == expected.choices
    assert dict(result.metadata) == dict(expected.metadata)


def test_coordinator_merges_secondary_contributions() -> None:
    """Secondary agents can append narration and metadata to the primary event."""

    world = WorldState()
    scripted_engine = ScriptedStoryEngine()
    extra_choice = StoryChoice("hum", "Hum along with the ambient sounds.")
    secondary = StubAgent(
        "ambient",
        narration="A cold wind whispers through the trees.",
        choices=(extra_choice, StoryChoice("look", "Duplicate command ignored.")),
        metadata={"mood": "ominous"},
    )
    coordinator = MultiAgentCoordinator(
        ScriptedStoryAgent("narrator", scripted_engine),
        secondary_agents=[secondary],
    )

    event = coordinator.propose_event(world)

    assert secondary.triggers, "secondary agent should receive a trigger"
    follow_up = secondary.triggers[0]
    assert follow_up.kind == "story-event"
    assert follow_up.source_event is not None
    assert (
        follow_up.source_event.narration
        == scripted_engine.propose_event(WorldState()).narration
    )

    # Primary narration appears first followed by the secondary fragment.
    assert event.narration.startswith(scripted_engine.propose_event(WorldState()).narration)
    assert "A cold wind whispers through the trees." in event.narration

    commands = [choice.command for choice in event.choices]
    assert commands.count("look") == 1
    assert "hum" in commands

    metadata = dict(event.metadata)
    assert metadata["ambient:mood"] == "ominous"


def test_coordinator_rejects_duplicate_agent_names() -> None:
    """Agent names must be unique to avoid ambiguous metadata."""

    primary = ScriptedStoryAgent("dup", ScriptedStoryEngine())
    duplicate = StubAgent("dup", narration="Echo")

    with pytest.raises(ValueError):
        MultiAgentCoordinator(primary, secondary_agents=[duplicate])


def test_coordinator_routes_queued_messages_between_turns() -> None:
    """Queued triggers are replayed on the following turn for targeted agents."""

    world = WorldState()

    primary = SequencedAgent(
        "narrator",
        (
            AgentTurnResult(
                event=StoryEvent("Primary opens the scene."),
                messages=(
                    AgentTrigger(
                        kind="alert",
                        metadata={"target": "scout"},
                    ),
                ),
            ),
            AgentTurnResult(
                event=StoryEvent("Primary continues the tale."),
            ),
        ),
    )

    scout = SequencedAgent(
        "scout",
        (
            AgentTurnResult(event=StoryEvent("Scout echoes the main story.")),
            AgentTurnResult(event=StoryEvent("Scout whispers a warning.")),
            AgentTurnResult(event=StoryEvent("Scout continues commentary.")),
        ),
    )

    coordinator = MultiAgentCoordinator(primary, secondary_agents=[scout])

    first_event = coordinator.propose_event(world)
    assert [trigger.kind for trigger in scout.triggers] == ["story-event"]
    assert "Primary opens the scene." in first_event.narration
    assert "Scout echoes the main story." in first_event.narration

    second_event = coordinator.propose_event(world)
    assert [trigger.kind for trigger in scout.triggers] == [
        "story-event",
        "alert",
        "story-event",
    ]

    narration = second_event.narration
    assert narration.startswith("Primary continues the tale.")
    assert "Scout whispers a warning." in narration
    assert "Scout continues commentary." in narration


def test_coordinator_debug_snapshot_reports_queued_messages() -> None:
    """Queued triggers should be surfaced through the debug snapshot."""

    world = WorldState()

    primary = SequencedAgent(
        "narrator",
        (
            AgentTurnResult(
                event=StoryEvent(
                    "Primary narrates the opening.",
                    choices=(StoryChoice("wait", "Wait"),),
                    metadata={"mood": "tense"},
                ),
                messages=(
                    AgentTrigger(
                        kind="alert",
                        metadata={"target": "scout", "note": "prepare"},
                        memory_request=MemoryRequest(action_limit=2),
                    ),
                ),
            ),
            AgentTurnResult(event=StoryEvent("Primary follows up.")),
        ),
    )

    scout = SequencedAgent(
        "scout",
        (
            AgentTurnResult(event=StoryEvent("Scout responds.")),
            AgentTurnResult(event=StoryEvent("Scout reacts to alert.")),
            AgentTurnResult(event=StoryEvent("Scout concludes.")),
        ),
    )

    coordinator = MultiAgentCoordinator(primary, secondary_agents=[scout])

    coordinator.propose_event(world)

    snapshot = coordinator.debug_snapshot()
    assert len(snapshot.queued_messages) == 1
    queued = snapshot.queued_messages[0]
    assert isinstance(queued, QueuedAgentMessage)
    assert queued.origin_agent == "narrator"
    assert queued.trigger_kind == "alert"
    assert queued.player_input is None
    assert dict(queued.metadata) == {"note": "prepare", "target": "scout"}
    assert queued.memory_request == MemoryRequest(action_limit=2)

    with pytest.raises(TypeError):
        queued.metadata["target"] = "other"  # type: ignore[index]

    # Mutating the coordinator should not affect captured snapshots.
    coordinator.propose_event(world)
    assert len(snapshot.queued_messages) == 1
    assert coordinator.debug_snapshot().queued_messages == ()
