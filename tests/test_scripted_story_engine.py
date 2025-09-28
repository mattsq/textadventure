"""Tests for the `ScriptedStoryEngine` concrete implementation."""

from __future__ import annotations

from importlib import resources

import pytest

from textadventure import WorldState
from textadventure.scripted_story_engine import (
    ScriptedStoryEngine,
    load_scenes_from_file,
    load_scenes_from_mapping,
)


def test_initial_event_describes_location() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world)

    assert "trailhead" in event.narration
    commands = event.iter_choice_commands()
    assert "look" in commands
    assert "recall" in commands


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


def test_recall_command_reports_recent_actions() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    world.remember_action("look")
    world.remember_action("explore the gate")

    event = engine.propose_event(world, player_input="recall")

    assert "reflect on your recent decisions" in event.narration.lower()
    assert "look" in event.narration
    assert "explore the gate" in event.narration


def test_tool_command_returns_lore_entry() -> None:
    world = WorldState(location="old-gate")
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="guide gate")

    assert "stone gate" in event.narration.lower()
    assert event.metadata["tool"] == "Field Guide"
    assert event.metadata["status"] == "ok"


def test_tool_command_prompts_for_topic_when_missing_argument() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="guide")

    assert "need a topic" in event.narration.lower()
    assert event.metadata["status"] == "missing_query"


def test_load_scenes_from_file_matches_default() -> None:
    data_path = resources.files("textadventure.data").joinpath("scripted_scenes.json")
    scenes = load_scenes_from_file(str(data_path))
    world = WorldState()
    engine = ScriptedStoryEngine(scenes=scenes)

    event = engine.propose_event(world)

    assert "trailhead" in event.narration
    assert "guide" in event.iter_choice_commands()


def test_duplicate_choice_commands_raise_error() -> None:
    scene_definitions = {
        "start": {
            "description": "A clearing.",
            "choices": [
                {"command": "look", "description": "Look around."},
                {"command": "look", "description": "Stare harder."},
            ],
            "transitions": {
                "look": {"narration": "You see trees."},
            },
        }
    }

    with pytest.raises(ValueError) as excinfo:
        load_scenes_from_mapping(scene_definitions)

    assert "duplicate" in str(excinfo.value)


def test_missing_transition_target_raises_error() -> None:
    scene_definitions = {
        "start": {
            "description": "A crossroads.",
            "choices": [
                {"command": "north", "description": "Head north."},
            ],
            "transitions": {
                "north": {"narration": "You walk onward.", "target": "unknown"},
            },
        }
    }

    with pytest.raises(ValueError) as excinfo:
        load_scenes_from_mapping(scene_definitions)

    assert "unknown target" in str(excinfo.value)
