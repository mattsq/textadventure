from textadventure.testing_toolkit import set_history, set_inventory
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
