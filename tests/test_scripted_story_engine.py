"""Tests for the `ScriptedStoryEngine` concrete implementation."""

from __future__ import annotations

from textadventure import WorldState
from textadventure.scripted_story_engine import ScriptedStoryEngine


def test_initial_event_describes_location() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world)

    assert "trailhead" in event.narration
    assert "look" in event.iter_choice_commands()


def test_explore_transitions_to_gate() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="explore")

    assert world.location == "old-gate"
    assert "gate" in event.narration.lower()
    assert "courtyard" in event.narration.lower()


def test_inspect_collects_key_once() -> None:
    world = WorldState(location="old-gate")
    engine = ScriptedStoryEngine()

    first_event = engine.propose_event(world, player_input="inspect")
    second_event = engine.propose_event(world, player_input="inspect")

    assert "rusty key" in world.inventory
    assert "tuck the rusty key" in first_event.narration
    assert "already have" in second_event.narration


def test_unknown_command_reprompts() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="dance")

    assert "not sure" in event.narration.lower()
    assert "dance" in event.narration
