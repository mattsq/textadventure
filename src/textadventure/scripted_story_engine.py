"""A tiny, scripted story engine used for manual exploration and tests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from .story_engine import StoryChoice, StoryEngine, StoryEvent
from .tools import KnowledgeBaseTool, Tool
from .world_state import WorldState


@dataclass(frozen=True)
class _Transition:
    """Description of how a command updates the world and narrative."""

    narration: str
    target: str | None = None
    item: str | None = None


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


def load_scenes_from_mapping(definitions: Mapping[str, Any]) -> MutableMapping[str, _Scene]:
    """Convert a mapping of scene definitions into internal `_Scene` objects.

    The ``definitions`` mapping is typically produced by parsing a JSON file.
    Each entry should contain ``description`` (str), ``choices`` (sequence of
    mappings with ``command``/``description`` keys) and ``transitions`` (mapping
    of command to narration/optional target/item metadata).
    """

    scenes: dict[str, _Scene] = {}

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
            choices.append(StoryChoice(command, description_text))

        raw_transitions = payload.get("transitions")
        if not isinstance(raw_transitions, Mapping):
            raise ValueError(f"Scene '{location}' must define a mapping of transitions.")

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

            item = transition_payload.get("item")
            if item is not None and not isinstance(item, str):
                raise ValueError(
                    f"Transition '{command}' in scene '{location}' must use a string 'item'."
                )

            transitions[command] = _Transition(
                narration=narration,
                target=target,
                item=item,
            )

        scenes[location] = _Scene(
            description=description,
            choices=tuple(choices),
            transitions=transitions,
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

    data_resource = resources.files("textadventure.data").joinpath("scripted_scenes.json")
    with data_resource.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    if not isinstance(raw_data, Mapping):
        raise ValueError("Bundled scenes must contain an object at the top level.")

    return load_scenes_from_mapping(raw_data)


_DEFAULT_SCENES: MutableMapping[str, _Scene] = _load_default_scenes()


class ScriptedStoryEngine(StoryEngine):
    """A deterministic `StoryEngine` with two handcrafted locations."""

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
                f"You're not sure how to '{cleaned_input}'. " f"Try one of: {available}."
            )
            return StoryEvent(narration=narration, choices=scene.choices)

        narration = transition.narration

        if transition.item:
            newly_added = world_state.add_item(transition.item)
            if newly_added:
                narration += f"\n\nYou tuck the {transition.item} safely away."
            else:
                narration += f"\n\nYou already have the {transition.item}."

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
        },
    ),
}


__all__ = [
    "ScriptedStoryEngine",
    "load_scenes_from_file",
    "load_scenes_from_mapping",
]
