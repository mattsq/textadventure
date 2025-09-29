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


def test_journal_command_reports_recent_history() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    for index in range(6):
        world.record_event(f"Logged event {index}")

    event = engine.propose_event(world, player_input="journal")

    assert "flip through your journal" in event.narration.lower()
    assert "- Logged event 1" in event.narration
    assert "- Logged event 5" in event.narration
    assert "- Logged event 0" not in event.narration


def test_journal_command_handles_empty_history() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="journal")

    assert "journal is blank" in event.narration.lower()


def test_inventory_command_summarises_sorted_items() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    world.add_item("weathered map")
    world.add_item("sunstone lens")

    event = engine.propose_event(world, player_input="inventory")

    assert "your pack currently holds" in event.narration.lower()
    assert "sunstone lens" in event.narration
    assert "weathered map" in event.narration
    assert event.narration.index("sunstone lens") < event.narration.index(
        "weathered map"
    )


def test_inventory_command_handles_empty_pack() -> None:
    world = WorldState()
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="inventory")

    assert "find nothing" in event.narration.lower()


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
    commands = event.iter_choice_commands()
    assert "guide" in commands
    assert "camp" in commands


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


def test_locked_hall_requires_key() -> None:
    world = WorldState(location="misty-courtyard")
    engine = ScriptedStoryEngine()

    failure_event = engine.propose_event(world, player_input="hall")

    assert "door refuses" in failure_event.narration.lower()
    assert world.location == "misty-courtyard"

    world.add_item("rusty key")

    success_event = engine.propose_event(world, player_input="hall")

    assert world.location == "collapsed-hall"
    assert "fallen pillars" in success_event.narration.lower()


def test_ranger_training_grants_signal_lesson() -> None:
    world = WorldState(location="ranger-lookout")
    engine = ScriptedStoryEngine()

    event = engine.propose_event(world, player_input="train")

    assert "signal" in event.narration.lower()
    assert "signal lesson" in world.inventory


def test_signal_practice_uses_conditional_narration() -> None:
    world = WorldState(location="ranger-lookout")
    engine = ScriptedStoryEngine()

    before_training = engine.propose_event(world, player_input="signal")
    assert "without proper guidance" in before_training.narration
    assert "Practiced the ranger signal" not in world.history

    engine.propose_event(world, player_input="train")

    after_training = engine.propose_event(world, player_input="signal")
    assert "echo the final note" in after_training.narration
    assert "Practiced the ranger signal" in world.history


def test_crypt_requires_signal_lesson() -> None:
    world = WorldState(location="collapsed-hall")
    engine = ScriptedStoryEngine()

    failure_event = engine.propose_event(world, player_input="crypt")

    assert "ranger's signal" in failure_event.narration.lower()
    assert world.location == "collapsed-hall"

    world.add_item("signal lesson")

    success_event = engine.propose_event(world, player_input="crypt")

    assert world.location == "sealed-crypt"
    assert "practiced signal" in success_event.narration.lower()


def test_crafting_consumes_components() -> None:
    world = WorldState(location="astral-workshop")
    engine = ScriptedStoryEngine()

    world.add_item("echo shard")
    world.add_item("luminous filament")

    event = engine.propose_event(world, player_input="craft")

    assert "resonant chime" in world.inventory
    assert "echo shard" not in world.inventory
    assert "luminous filament" not in world.inventory
    assert "weave the filament" in event.narration.lower()


def test_observatory_activation_requires_items() -> None:
    world = WorldState(location="celestial-observatory")
    engine = ScriptedStoryEngine()

    failure_event = engine.propose_event(world, player_input="activate")

    assert "expects both the sunstone lens" in failure_event.narration
    assert world.location == "celestial-observatory"

    world.add_item("sunstone lens")
    world.add_item("resonant chime")

    success_event = engine.propose_event(world, player_input="activate")

    assert "pathways of light" in success_event.narration.lower()


def test_archives_study_requires_map() -> None:
    world = WorldState(location="flooded-archives")
    engine = ScriptedStoryEngine()

    failure_event = engine.propose_event(world, player_input="study")

    assert "weathered map" in failure_event.narration.lower()
    assert world.location == "flooded-archives"

    world.add_item("weathered map")

    success_event = engine.propose_event(world, player_input="study")

    assert "hidden annotations" in success_event.narration.lower()
