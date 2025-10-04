import pytest

from textadventure.testing_toolkit import (
    WorldDebugSnapshot,
    debug_snapshot,
    jump_to_scene,
    set_history,
    set_inventory,
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
