"""A tiny, scripted story engine used for manual exploration and tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping

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


_DEFAULT_SCENES: MutableMapping[str, _Scene] = {
    "starting-area": _Scene(
        description=(
            "Sunlight filters through tall trees at the forest trailhead. "
            "An old stone gate lies to the north, its archway draped in moss."
        ),
        choices=(
            StoryChoice("look", "Take in the surroundings."),
            StoryChoice("explore", "Head toward the mossy gate."),
            StoryChoice("inventory", "Check what you're carrying."),
            StoryChoice("journal", "Review the notes in your journal."),
            StoryChoice("recall", "Reflect on your recent decisions."),
            StoryChoice(
                "guide",
                "Consult the field guide for lore (e.g. 'guide gate').",
            ),
        ),
        transitions={
            "look": _Transition(
                narration="You pause and listen to the rustling leaves."
            ),
            "explore": _Transition(
                narration="You follow the worn path toward the gate.",
                target="old-gate",
            ),
        },
    ),
    "old-gate": _Scene(
        description=(
            "The gate stands ajar, revealing a courtyard blanketed in mist. "
            "A rusty key glints between the stones nearby."
        ),
        choices=(
            StoryChoice("look", "Study the ancient masonry."),
            StoryChoice("inspect", "Investigate the glinting object."),
            StoryChoice("return", "Head back down the forest trail."),
            StoryChoice("inventory", "Check your belongings."),
            StoryChoice("journal", "Look over your recorded memories."),
            StoryChoice("recall", "Reflect on your recent decisions."),
            StoryChoice(
                "guide",
                "Consult the field guide for lore (e.g. 'guide gate').",
            ),
        ),
        transitions={
            "look": _Transition(
                narration="Time has scarred the gate, but it still stands firm."
            ),
            "inspect": _Transition(
                narration="You kneel and pick up the rusty key.",
                item="rusty key",
            ),
            "return": _Transition(
                narration="You retrace your steps to the trailhead.",
                target="starting-area",
            ),
        },
    ),
}


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


__all__ = ["ScriptedStoryEngine"]
