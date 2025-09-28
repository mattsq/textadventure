"""Unit tests for the :mod:`textadventure.world_state` module."""

import pytest

from textadventure import WorldState


@pytest.fixture()
def world_state() -> WorldState:
    return WorldState(location="Atrium")


def test_move_to_updates_location_and_records_event(world_state: WorldState) -> None:
    world_state.move_to("Observatory")

    assert world_state.location == "Observatory"
    assert world_state.history[-1] == "Moved to Observatory"


def test_move_to_ignores_redundant_moves(world_state: WorldState) -> None:
    world_state.move_to("Atrium")

    assert world_state.location == "Atrium"
    assert world_state.history == []


def test_add_and_remove_items_track_inventory_and_history(
    world_state: WorldState,
) -> None:
    added = world_state.add_item("Ancient Key")
    removed = world_state.remove_item("Ancient Key")

    assert added is True
    assert removed is True
    assert "Ancient Key" not in world_state.inventory
    assert world_state.history == [
        "Picked up Ancient Key",
        "Dropped Ancient Key",
    ]


def test_add_item_returns_false_when_duplicate(world_state: WorldState) -> None:
    world_state.add_item("Lantern")

    result = world_state.add_item("Lantern")

    assert result is False
    assert world_state.history == ["Picked up Lantern"]


def test_record_event_validates_description(world_state: WorldState) -> None:
    with pytest.raises(ValueError):
        world_state.record_event("   ")


def test_remove_item_returns_false_when_absent(world_state: WorldState) -> None:
    result = world_state.remove_item("Map")

    assert result is False
    assert world_state.history == []


def test_recent_actions_reflect_recorded_memory(world_state: WorldState) -> None:
    world_state.remember_action("Open the gate")
    world_state.remember_action("Step through")

    assert world_state.recent_actions() == ("Open the gate", "Step through")


def test_recent_observations_reflect_story_notes(world_state: WorldState) -> None:
    world_state.remember_observation("A lantern flickers in the dusk.")

    assert world_state.recent_observations(limit=1) == ("A lantern flickers in the dusk.",)
