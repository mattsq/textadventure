"""Tests for the multi-agent coordinator prototype."""

from __future__ import annotations

import pytest

from textadventure.multi_agent import (
    Agent,
    AgentTrigger,
    AgentTurnResult,
    MultiAgentCoordinator,
    ScriptedStoryAgent,
)
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
