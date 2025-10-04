"""Helpers for manipulating ``WorldState`` instances during tests."""

from __future__ import annotations

from typing import Iterable

from .world_state import WorldState


__all__ = ["set_inventory", "set_history"]


def set_inventory(
    world: WorldState,
    items: Iterable[str],
    *,
    record_events: bool = False,
) -> None:
    """Replace the inventory contents with the provided collection of items.

    The helper removes any items that are not present in ``items`` and adds
    any missing entries while respecting the original order of the iterable.
    Duplicate values are ignored so the resulting inventory contains each item
    at most once. When ``record_events`` is true the helper emits history
    entries that mirror manual ``add_item``/``remove_item`` calls.
    """

    seen: set[str] = set()
    target_order: list[str] = []
    for raw_item in items:
        validated = WorldState._validate_label(raw_item, "item")
        if validated not in seen:
            seen.add(validated)
            target_order.append(validated)

    target_items = set(target_order)
    current_items = set(world.inventory)

    for item in sorted(current_items - target_items):
        world.remove_item(item, record_event=record_events)
        current_items.remove(item)

    for item in target_order:
        if item not in current_items:
            world.add_item(item, record_event=record_events)
            current_items.add(item)


def set_history(world: WorldState, events: Iterable[str]) -> None:
    """Replace the history log with the supplied event descriptions."""

    world.history.clear()
    world.extend_history(events)
