"""Helpers for manipulating ``WorldState`` instances during tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .world_state import WorldState
from .story_engine import StoryEngine, StoryEvent


@dataclass(frozen=True)
class WorldDebugSnapshot:
    """Structured view of a world's internal state for debugging."""

    location: str
    inventory: tuple[str, ...]
    history: tuple[str, ...]
    recent_actions: tuple[str, ...]
    recent_observations: tuple[str, ...]


__all__ = [
    "WorldDebugSnapshot",
    "set_inventory",
    "set_history",
    "jump_to_scene",
    "debug_snapshot",
    "StepResult",
    "step_through",
]


@dataclass(frozen=True)
class StepResult:
    """Outcome of a single story engine step."""

    command: str | None
    event: StoryEvent


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


def jump_to_scene(
    world: WorldState,
    scene_id: str,
    *,
    record_event: bool = False,
) -> None:
    """Move ``world`` to ``scene_id`` without needing to play through choices.

    The helper delegates to :meth:`WorldState.move_to` so validation rules are
    preserved. Tests can opt-in to history tracking via ``record_event`` to
    mirror real navigation, but the default leaves the history untouched so the
    helper can be used for deterministic setup.
    """

    world.move_to(scene_id, record_event=record_event)


def debug_snapshot(
    world: WorldState,
    *,
    action_limit: int = 5,
    observation_limit: int = 5,
) -> WorldDebugSnapshot:
    """Capture a deterministic snapshot of ``world`` for debugging.

    The snapshot summarises the player's location, inventory, and history along
    with the most recent memories. Inventory entries are sorted to provide
    stable comparisons in assertions or golden snapshots.

    Args:
        world: The ``WorldState`` instance to introspect.
        action_limit: Maximum number of recent player actions to include. Must
            be a non-negative integer.
        observation_limit: Maximum number of recent observations to include.
            Must be a non-negative integer.
    """

    if action_limit < 0:
        raise ValueError("action_limit must be non-negative")
    if observation_limit < 0:
        raise ValueError("observation_limit must be non-negative")

    return WorldDebugSnapshot(
        location=world.location,
        inventory=tuple(sorted(world.inventory)),
        history=tuple(world.history),
        recent_actions=tuple(world.recent_actions(limit=action_limit)),
        recent_observations=tuple(world.recent_observations(limit=observation_limit)),
    )


def step_through(
    engine: StoryEngine,
    world: WorldState,
    commands: Iterable[str],
    *,
    record_memory: bool = True,
) -> Sequence[StepResult]:
    """Execute a series of player commands one step at a time."""

    def _capture(event: StoryEvent, command: str | None) -> None:
        if record_memory:
            world.remember_observation(event.narration)
        steps.append(StepResult(command=command, event=event))

    steps: list[StepResult] = []

    initial_event = engine.propose_event(world)
    _capture(initial_event, None)
    current_event = initial_event

    for raw_command in commands:
        if not current_event.has_choices:
            raise RuntimeError(
                "No further commands can be processed: the latest event offered no choices."
            )
        if not isinstance(raw_command, str):
            raise TypeError(
                "Commands must be strings when using step_through for scripted execution."
            )

        command = raw_command.strip()
        if not command:
            raise ValueError(
                "Commands must be non-empty strings after trimming whitespace."
            )

        available_commands = current_event.iter_choice_commands()
        lowered = command.lower()
        if available_commands and lowered not in available_commands:
            formatted = ", ".join(available_commands) or "(none)"
            raise ValueError(
                f"Command '{command}' is not available. Choose from: {formatted}."
            )

        if record_memory:
            world.remember_action(command)

        current_event = engine.propose_event(world, player_input=command)
        _capture(current_event, command)

    return tuple(steps)
