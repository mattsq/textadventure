"""Tests for the story engine abstractions."""

from __future__ import annotations

import pytest

from textadventure import StoryChoice, StoryEngine, StoryEvent, WorldState


class DummyStoryEngine(StoryEngine):
    """Simple concrete implementation used for exercising the interface."""

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        narration = f"You are at {world_state.location}."
        choices = [StoryChoice("Look", "Survey the area")]
        return StoryEvent(narration=narration, choices=choices)


def test_story_choice_normalises_fields() -> None:
    choice = StoryChoice("  Examine  ", "  Inspect the room  ")

    assert choice.command == "examine"
    assert choice.description == "Inspect the room"


def test_story_event_rejects_duplicate_choice_commands() -> None:
    with pytest.raises(ValueError):
        StoryEvent(
            narration="A fork in the road.",
            choices=[
                StoryChoice("Left", "Head into the forest"),
                StoryChoice("left", "Take the same path again"),
            ],
        )


def test_metadata_is_immutable_mapping() -> None:
    event = StoryEvent(
        narration="A mysterious wind howls.",
        metadata={" mood ": " ominous "},
    )

    assert dict(event.metadata) == {"mood": "ominous"}
    with pytest.raises(TypeError):
        event.metadata["mood"] = "calm"  # type: ignore[index]


def test_story_engine_format_event() -> None:
    engine = DummyStoryEngine()
    world = WorldState(location="clifftop")
    event = engine.propose_event(world)

    formatted = engine.format_event(event)

    assert "You are at clifftop." in formatted
    assert "[examine]" not in formatted
    assert "[look]" in formatted
    assert "Survey the area" in formatted


def test_story_engine_format_event_renders_markdown() -> None:
    engine = DummyStoryEngine()
    event = StoryEvent(
        narration="You witness **something** remarkable.",
        choices=[StoryChoice("Inspect", "Study the *details* carefully.")],
    )

    formatted = engine.format_event(event)

    assert "\033[1msomething\033[0m" in formatted
    assert "\033[3mdetails\033[0m" in formatted
