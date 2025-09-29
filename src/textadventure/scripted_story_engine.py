"""A tiny, scripted story engine used for manual exploration and tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, MutableMapping

from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .tools import KnowledgeBaseTool, Tool
from .world_state import WorldState


@dataclass(frozen=True)
class _ConditionalNarration:
    """Narration override that activates when conditions are satisfied."""

    narration: str
    requires_history_all: tuple[str, ...] = ()
    requires_history_any: tuple[str, ...] = ()
    forbids_history_any: tuple[str, ...] = ()
    requires_inventory_all: tuple[str, ...] = ()
    requires_inventory_any: tuple[str, ...] = ()
    forbids_inventory_any: tuple[str, ...] = ()
    records: tuple[str, ...] = ()

    def matches(self, world_state: WorldState) -> bool:
        """Return ``True`` when the world state satisfies all constraints."""

        history_entries = set(world_state.history)
        inventory_entries = world_state.inventory

        if self.requires_history_all and not all(
            entry in history_entries for entry in self.requires_history_all
        ):
            return False
        if self.requires_history_any and not any(
            entry in history_entries for entry in self.requires_history_any
        ):
            return False
        if self.forbids_history_any and any(
            entry in history_entries for entry in self.forbids_history_any
        ):
            return False

        if self.requires_inventory_all and not all(
            item in inventory_entries for item in self.requires_inventory_all
        ):
            return False
        if self.requires_inventory_any and not any(
            item in inventory_entries for item in self.requires_inventory_any
        ):
            return False
        if self.forbids_inventory_any and any(
            item in inventory_entries for item in self.forbids_inventory_any
        ):
            return False

        return True


@dataclass(frozen=True)
class _Transition:
    """Description of how a command updates the world and narrative."""

    narration: str
    target: str | None = None
    item: str | None = None
    requires: tuple[str, ...] = ()
    failure_narration: str | None = None
    consumes: tuple[str, ...] = ()
    records: tuple[str, ...] = ()
    narration_overrides: tuple[_ConditionalNarration, ...] = ()


@dataclass(frozen=True)
class _Scene:
    """Container describing a location and its available actions."""

    description: str
    choices: tuple[StoryChoice, ...]
    transitions: Mapping[str, _Transition]

    def command_list(self) -> str:
        return ", ".join(choice.command for choice in self.choices)


def _history_summary(world_state: WorldState) -> str:
    if not world_state.history:
        return "Your journal is blank—for now."

    entries = "\n".join(f"- {entry}" for entry in world_state.history[-5:])
    return f"You flip through your journal and read:\n{entries}"


def _inventory_summary(world_state: WorldState) -> str:
    if not world_state.inventory:
        return "You pat your pockets but find nothing of note."

    items = ", ".join(sorted(world_state.inventory))
    return f"Your pack currently holds: {items}."


def _memory_summary(world_state: WorldState) -> str:
    recent_actions = world_state.recent_actions()
    if not recent_actions:
        return "You search your thoughts but recall no deliberate choices yet."

    entries = "\n".join(f"- {action}" for action in recent_actions)
    return f"You reflect on your recent decisions:\n{entries}"


def _coerce_string_list(value: Any, *, error_message: str) -> tuple[str, ...]:
    """Normalize optional string sequences into tuples.

    Args:
        value: The raw value extracted from a JSON definition.
        error_message: Error to raise when the value is not a list of strings.
    """

    if value is None:
        return ()
    if isinstance(value, list) and all(isinstance(entry, str) for entry in value):
        return tuple(entry for entry in value)
    raise ValueError(error_message)


def load_scenes_from_mapping(
    definitions: Mapping[str, Any],
) -> MutableMapping[str, _Scene]:
    """Convert a mapping of scene definitions into internal `_Scene` objects.

    The ``definitions`` mapping is typically produced by parsing a JSON file.
    Each entry should contain ``description`` (str), ``choices`` (sequence of
    mappings with ``command``/``description`` keys) and ``transitions`` (mapping
    of command to narration/optional target/item metadata).
    """

    scenes: dict[str, _Scene] = {}
    pending_targets: list[tuple[str, str]] = []

    for location, payload in definitions.items():
        if not isinstance(location, str):
            raise ValueError("Scene keys must be strings.")
        if not isinstance(payload, Mapping):
            raise ValueError(f"Scene '{location}' must map to an object definition.")

        description = payload.get("description")
        if not isinstance(description, str):
            raise ValueError(f"Scene '{location}' is missing a text description.")

        raw_choices = payload.get("choices")
        if not isinstance(raw_choices, list):
            raise ValueError(f"Scene '{location}' must define a list of choices.")

        choices: list[StoryChoice] = []
        seen_commands: set[str] = set()
        for index, choice_payload in enumerate(raw_choices):
            if not isinstance(choice_payload, Mapping):
                raise ValueError(
                    f"Choice #{index} in scene '{location}' must be an object definition."
                )

            command = choice_payload.get("command")
            description_text = choice_payload.get("description")
            if not isinstance(command, str) or not isinstance(description_text, str):
                raise ValueError(
                    f"Choice #{index} in scene '{location}' must provide 'command' and 'description' strings."
                )
            if command in seen_commands:
                raise ValueError(
                    f"Scene '{location}' defines duplicate choice command '{command}'."
                )
            seen_commands.add(command)
            choices.append(StoryChoice(command, description_text))

        raw_transitions = payload.get("transitions")
        if not isinstance(raw_transitions, Mapping):
            raise ValueError(
                f"Scene '{location}' must define a mapping of transitions."
            )

        transitions: dict[str, _Transition] = {}
        for command, transition_payload in raw_transitions.items():
            if not isinstance(command, str):
                raise ValueError(
                    f"Transition command keys must be strings in scene '{location}'."
                )
            if not isinstance(transition_payload, Mapping):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must map to an object definition."
                )

            narration = transition_payload.get("narration")
            if not isinstance(narration, str):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' requires a narration string."
                )

            target = transition_payload.get("target")
            if target is not None and not isinstance(target, str):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must use a string 'target'."
                )
            if target:
                pending_targets.append((location, target))

            item = transition_payload.get("item")
            if item is not None and not isinstance(item, str):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must use a string 'item'."
                )

            raw_requires = transition_payload.get("requires")
            requires: tuple[str, ...]
            if raw_requires is None:
                requires = ()
            elif isinstance(raw_requires, list) and all(
                isinstance(entry, str) for entry in raw_requires
            ):
                requires = tuple(entry for entry in raw_requires)
            else:
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must define 'requires' as a list of strings."
                )

            failure_narration = transition_payload.get("failure_narration")
            if failure_narration is not None and not isinstance(failure_narration, str):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must use a string 'failure_narration'."
                )

            raw_consumes = transition_payload.get("consumes")
            consumes: tuple[str, ...]
            if raw_consumes is None:
                consumes = ()
            elif isinstance(raw_consumes, list) and all(
                isinstance(entry, str) for entry in raw_consumes
            ):
                consumes = tuple(entry for entry in raw_consumes)
            else:
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must define 'consumes' as a list of strings."
                )

            records = _coerce_string_list(
                transition_payload.get("records"),
                error_message=(
                    f"Transition '{command}' in scene '{location}' must define 'records' as a list of strings."
                ),
            )

            raw_overrides = transition_payload.get("narration_overrides")
            overrides: list[_ConditionalNarration] = []
            if raw_overrides is not None:
                if not isinstance(raw_overrides, list):
                    raise ValueError(
                        f"Transition '{command}' in scene '{location}' must define 'narration_overrides' as a list."
                    )
                for index, override_payload in enumerate(raw_overrides):
                    if not isinstance(override_payload, Mapping):
                        raise ValueError(
                            "Transition '{}' in scene '{}' narration override #{} must be an object definition.".format(
                                command, location, index
                            )
                        )

                    override_narration = override_payload.get("narration")
                    if not isinstance(override_narration, str):
                        raise ValueError(
                            "Transition '{}' in scene '{}' narration override #{} must provide a narration string.".format(
                                command, location, index
                            )
                        )

                    requires_history_all = _coerce_string_list(
                        override_payload.get("requires_history_all"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'requires_history_all' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    requires_history_any = _coerce_string_list(
                        override_payload.get("requires_history_any"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'requires_history_any' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    forbids_history_any = _coerce_string_list(
                        override_payload.get("forbids_history_any"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'forbids_history_any' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    requires_inventory_all = _coerce_string_list(
                        override_payload.get("requires_inventory_all"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'requires_inventory_all' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    requires_inventory_any = _coerce_string_list(
                        override_payload.get("requires_inventory_any"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'requires_inventory_any' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    forbids_inventory_any = _coerce_string_list(
                        override_payload.get("forbids_inventory_any"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'forbids_inventory_any' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )
                    override_records = _coerce_string_list(
                        override_payload.get("records"),
                        error_message=(
                            "Transition '{}' in scene '{}' narration override #{} must define 'records' as a list of strings.".format(
                                command, location, index
                            )
                        ),
                    )

                    overrides.append(
                        _ConditionalNarration(
                            narration=override_narration,
                            requires_history_all=requires_history_all,
                            requires_history_any=requires_history_any,
                            forbids_history_any=forbids_history_any,
                            requires_inventory_all=requires_inventory_all,
                            requires_inventory_any=requires_inventory_any,
                            forbids_inventory_any=forbids_inventory_any,
                            records=override_records,
                        )
                    )

            transitions[command] = _Transition(
                narration=narration,
                target=target,
                item=item,
                requires=requires,
                failure_narration=failure_narration,
                consumes=consumes,
                records=records,
                narration_overrides=tuple(overrides),
            )

        scenes[location] = _Scene(
            description=description,
            choices=tuple(choices),
            transitions=transitions,
        )

    for location, target in pending_targets:
        if target not in scenes:
            raise ValueError(
                f"Scene '{location}' transitions to unknown target '{target}'."
            )

    return scenes


def load_scenes_from_file(path: str | Path) -> MutableMapping[str, _Scene]:
    """Load scene definitions from a JSON file on disk."""

    data_path = Path(path)
    with data_path.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    if not isinstance(raw_data, Mapping):
        raise ValueError("Scene files must contain an object at the top level.")

    return load_scenes_from_mapping(raw_data)


def _load_default_scenes() -> MutableMapping[str, _Scene]:
    """Read the bundled demo scenes from the package data directory."""

    data_resource = resources.files("textadventure.data").joinpath(
        "scripted_scenes.json"
    )
    with data_resource.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    if not isinstance(raw_data, Mapping):
        raise ValueError("Bundled scenes must contain an object at the top level.")

    return load_scenes_from_mapping(raw_data)


_DEFAULT_SCENES: MutableMapping[str, _Scene] = _load_default_scenes()


class ScriptedStoryEngine(StoryEngine):
    """A deterministic `StoryEngine` backed by bundled demo scenes."""

    def __init__(
        self,
        *,
        scenes: Mapping[str, _Scene] | None = None,
        tools: Mapping[str, Tool] | None = None,
    ):
        """Create a scripted engine with optional custom scenes and tools.

        The ``tools`` mapping associates input commands (e.g. ``"guide"``)
        with :class:`~textadventure.tools.Tool` instances. When a player's
        input begins with a registered command the corresponding tool is
        invoked with the remainder of the input as its query. The resulting
        :class:`~textadventure.tools.ToolResponse` is converted into a
        :class:`~textadventure.story_engine.StoryEvent` so that tools can
        participate in the narrative loop alongside scripted transitions.
        """
        if scenes is None:
            scenes = _DEFAULT_SCENES
        if tools is None:
            tools = _DEFAULT_TOOLS
        self._scenes: Mapping[str, _Scene] = scenes
        self._tools: Mapping[str, Tool] = tools

    @property
    def scenes(self) -> Mapping[str, _Scene]:
        """Return a read-only view of the configured scenes."""

        return MappingProxyType(self._scenes)

    def propose_event(
        self,
        world_state: WorldState,
        *,
        player_input: str | None = None,
    ) -> StoryEvent:
        scene = self._scenes.get(world_state.location)
        if scene is None:
            return StoryEvent(
                narration=(
                    "You find yourself in unfamiliar territory. "
                    "There are no scripted events for this location yet."
                ),
                choices=(),
            )

        if player_input is None:
            return StoryEvent(narration=scene.description, choices=scene.choices)

        cleaned_input = player_input.strip()
        if not cleaned_input:
            return StoryEvent(narration="Silence lingers...", choices=scene.choices)

        parts = cleaned_input.lower().split(maxsplit=1)
        command = parts[0]
        argument = parts[1] if len(parts) > 1 else ""

        if command == "journal":
            return StoryEvent(
                narration=_history_summary(world_state),
                choices=scene.choices,
            )

        if command == "inventory":
            return StoryEvent(
                narration=_inventory_summary(world_state),
                choices=scene.choices,
            )

        if command == "recall":
            return StoryEvent(
                narration=_memory_summary(world_state),
                choices=scene.choices,
            )

        tool = self._tools.get(command)
        if tool is not None:
            response = tool.invoke(argument, world_state=world_state)
            return StoryEvent(
                narration=response.narration,
                choices=scene.choices,
                metadata=response.metadata,
            )

        transition = scene.transitions.get(command)
        if transition is None:
            available = scene.command_list()
            narration = (
                f"You're not sure how to '{cleaned_input}'. "
                f"Try one of: {available}."
            )
            return StoryEvent(narration=narration, choices=scene.choices)

        missing_items = tuple(
            item for item in transition.requires if item not in world_state.inventory
        )
        if missing_items:
            if transition.failure_narration:
                narration = transition.failure_narration
            else:
                formatted = ", ".join(missing_items)
                narration = f"You need {formatted} before you can do that."
            return StoryEvent(narration=narration, choices=scene.choices)

        narration = transition.narration
        records_to_apply: list[str] = list(transition.records)
        for override in transition.narration_overrides:
            if override.matches(world_state):
                narration = override.narration
                if override.records:
                    records_to_apply.extend(override.records)
                break

        if transition.item:
            newly_added = world_state.add_item(transition.item)
            if newly_added:
                narration += f"\n\nYou tuck the {transition.item} safely away."
            else:
                narration += f"\n\nYou already have the {transition.item}."

        for item in transition.consumes:
            world_state.remove_item(item)

        if transition.target:
            world_state.move_to(transition.target)
            follow_up_scene = self._scenes.get(world_state.location)
            if follow_up_scene:
                narration = f"{narration}\n\n{follow_up_scene.description}"
                choices = follow_up_scene.choices
            else:
                choices = ()
        else:
            choices = scene.choices

        if records_to_apply:
            world_state.extend_history(records_to_apply)

        return StoryEvent(narration=narration, choices=choices)


_DEFAULT_TOOLS: Mapping[str, Tool] = {
    "guide": KnowledgeBaseTool(
        entries={
            "forest": (
                "The surrounding forest is part of the Evermoss Preserve, a"
                " sanctuary for ancient trees and the creatures that dwell"
                " within. Rangers whisper that the woods shift to guide"
                " friendly travelers."
            ),
            "gate": (
                "The stone gate predates the nearby settlement by centuries."
                " Its arch is said to resonate when moonlight and song"
                " coincide, revealing hidden doorways to other realms."
            ),
            "key": (
                "Keys forged in the old city rarely rust, yet this one bears"
                " a reddish patina. Legends hint that such keys respond to"
                " whispered passwords, revealing secret mechanisms."
            ),
            "camp": (
                "Scavengers established a semi-permanent camp to catalog"
                " relics from the bastion. Their annotated maps point toward"
                " sealed sectors and the safest paths between them."
            ),
            "lookout": (
                "The lookout predates the bastion's fall. Rangers still"
                " maintain it as a listening post and teach the resonant"
                " signal used to calm the guardians below."
            ),
            "courtyard": (
                "The misty courtyard acts as a nexus between the ruins'"
                " wings. Statues here attune to specific harmonies, hinting"
                " at the puzzles that await deeper within."
            ),
            "archives": (
                "Flooded though they are, the archives contain expedition"
                " reports and schematics etched to survive water damage. A"
                " proper map helps align the shelving system."
            ),
            "hall": (
                "Collapsed pillars once amplified ceremonial songs. The"
                " guardians respond to anyone who can reproduce the old"
                " ranger signal with confidence."
            ),
            "stair": (
                "The echoing stair doubles as an instrument. Travelers tune"
                " themselves to its harmonics before approaching the spire"
                " to avoid disturbing latent wards."
            ),
            "map": (
                "The weathered map layers annotations from generations of"
                " explorers. Marginalia reveal how certain frequencies"
                " interact with the spire's mechanisms."
            ),
            "lens": (
                "Sunstone lenses focus ambient aether into coherent beams."
                " They're essential for activating observatory equipment and"
                " are notoriously difficult to craft."
            ),
            "chime": (
                "Resonant chimes pair rare crystals with harmonic filaments."
                " When struck in sequence they pacify guardians and unlock"
                " sealed pathways."
            ),
            "sigil": (
                "Ancient sigils store ceremonial authority. Carrying one"
                " marks you as a recognized ally to the bastion's guardians"
                " and allows limited passage through their halls."
            ),
            "observatory": (
                "The celestial observatory channels starlight through"
                " suspended lenses. Only those who complete the bastion's"
                " resonant trials can align its arrays."
            ),
        },
    ),
}


__all__ = [
    "ScriptedStoryEngine",
    "load_scenes_from_file",
    "load_scenes_from_mapping",
]
