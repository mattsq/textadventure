import pytest

from textadventure.scripted_story_engine import ScriptedStoryEngine
from textadventure.story_engine import StoryChoice, StoryEngine, StoryEvent
from textadventure.testing_toolkit import (
    StepResult,
    WorldDebugSnapshot,
    debug_snapshot,
    jump_to_scene,
    set_history,
    set_inventory,
    step_through,
)
from textadventure.world_state import WorldState


def test_set_inventory_replaces_contents_without_history() -> None:
    world = WorldState()
    world.add_item("Lantern", record_event=False)
    world.add_item("Compass", record_event=False)

    set_inventory(world, ["Lantern", "Map", "Lantern"], record_events=False)

    assert world.inventory == {"Lantern", "Map"}
    assert world.history == []


def test_set_inventory_records_changes_when_requested() -> None:
    world = WorldState()
    world.add_item("Lantern", record_event=False)
    world.add_item("Compass", record_event=False)

    set_inventory(world, ["Map", "Lantern"], record_events=True)

    assert world.inventory == {"Lantern", "Map"}
    assert world.history == ["Dropped Compass", "Picked up Map"]


def test_set_history_replaces_event_log() -> None:
    world = WorldState()
    world.record_event("Original entry")

    set_history(world, ["  First action  ", "Second action"])

    assert world.history == ["First action", "Second action"]


def test_jump_to_scene_updates_location_without_history() -> None:
    world = WorldState()

    jump_to_scene(world, "mysterious-cavern")

    assert world.location == "mysterious-cavern"
    assert world.history == []


def test_jump_to_scene_can_record_history() -> None:
    world = WorldState()

    jump_to_scene(world, "sunlit-grove", record_event=True)

    assert world.location == "sunlit-grove"
    assert world.history == ["Moved to sunlit-grove"]


def test_debug_snapshot_exposes_world_details() -> None:
    world = WorldState()
    world.move_to("sunlit-grove", record_event=False)
    world.add_item("Lantern", record_event=False)
    world.add_item("Compass", record_event=False)
    world.record_event("Found a hidden alcove")
    world.remember_action("look around")
    world.remember_action("light lantern")
    world.remember_observation("The cavern glows warmly.")

    snapshot = debug_snapshot(world, action_limit=1)

    assert snapshot == WorldDebugSnapshot(
        location="sunlit-grove",
        inventory=("Compass", "Lantern"),
        history=("Found a hidden alcove",),
        recent_actions=("light lantern",),
        recent_observations=("The cavern glows warmly.",),
    )


def test_debug_snapshot_rejects_negative_limits() -> None:
    world = WorldState()

    with pytest.raises(ValueError):
        debug_snapshot(world, action_limit=-1)

    with pytest.raises(ValueError):
        debug_snapshot(world, observation_limit=-2)


class _StubEngine(StoryEngine):
    """Minimal story engine used for validating error handling."""

    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        del world_state
        self.calls.append(player_input)
        if player_input is None:
            return StoryEvent(
                narration="Opening scene.",
                choices=(StoryChoice("advance", "Move forward"),),
            )
        if player_input == "advance":
            return StoryEvent(narration="The path ends.")
        raise AssertionError(f"Unexpected command: {player_input}")


def test_step_through_executes_command_sequence_and_records_memory() -> None:
    engine = ScriptedStoryEngine()
    world = WorldState()

    steps = step_through(engine, world, ["explore", "look"])

    assert [step.command for step in steps] == [None, "explore", "look"]
    assert isinstance(steps[0], StepResult)
    assert "forest trailhead" in steps[0].event.narration
    assert "worn path" in steps[1].event.narration
    assert world.location == "old-gate"
    assert world.recent_actions() == ("explore", "look")
    observations = world.recent_observations(limit=3)
    assert len(observations) == 3
    assert observations[0].startswith("Sunlight filters through tall trees")
    assert observations[1].startswith("You follow the worn path")
    assert observations[2].startswith("Time has scarred the gate")


def test_step_through_rejects_unavailable_commands() -> None:
    engine = _StubEngine()
    world = WorldState()

    with pytest.raises(ValueError, match="Command 'invalid' is not available"):
        step_through(engine, world, ["invalid"])

    assert engine.calls == [None]


def test_step_through_requires_choices_to_continue() -> None:
    engine = _StubEngine()
    world = WorldState()

    with pytest.raises(RuntimeError):
        step_through(engine, world, ["advance", "again"])

    assert engine.calls == [None, "advance"]
