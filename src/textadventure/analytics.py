"""Utilities for analysing scripted adventures and estimating complexity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, cast

from .story_engine import StoryChoice


class _TransitionLike(Protocol):
    """Protocol describing the fields needed from transition objects."""

    target: str | None
    item: str | None
    requires: Sequence[str]
    consumes: Sequence[str]
    records: Sequence[str]
    narration_overrides: Sequence[object]


class _SceneLike(Protocol):
    """Protocol describing the subset of scene details required for metrics."""

    choices: Sequence[StoryChoice]
    transitions: Mapping[str, _TransitionLike]


@dataclass(frozen=True)
class AdventureComplexityMetrics:
    """Summary statistics describing the breadth of an adventure."""

    scene_count: int
    choice_count: int
    transition_count: int
    interactive_choice_count: int
    commands_without_transitions: int
    average_choices_per_scene: float
    average_transitions_per_scene: float
    max_choices_in_scene: int
    max_transitions_in_scene: int
    terminal_transition_count: int
    gated_transition_count: int
    conditional_transition_count: int
    item_reward_count: int
    unique_items_awarded: tuple[str, ...]
    unique_items_consumed: tuple[str, ...]
    unique_history_records: tuple[str, ...]

    @property
    def unique_item_reward_count(self) -> int:
        """Return the number of unique items that can be acquired."""

        return len(self.unique_items_awarded)

    @property
    def unique_item_consumption_count(self) -> int:
        """Return the number of unique items that can be consumed."""

        return len(self.unique_items_consumed)

    @property
    def unique_history_record_count(self) -> int:
        """Return the number of unique history entries that can be recorded."""

        return len(self.unique_history_records)


def _safe_average(total: int, count: int) -> float:
    if count == 0:
        return 0.0
    return total / count


def compute_adventure_complexity(
    scenes: Mapping[str, _SceneLike],
) -> AdventureComplexityMetrics:
    """Compute summary metrics for a collection of scripted scenes."""

    if not scenes:
        return AdventureComplexityMetrics(
            scene_count=0,
            choice_count=0,
            transition_count=0,
            interactive_choice_count=0,
            commands_without_transitions=0,
            average_choices_per_scene=0.0,
            average_transitions_per_scene=0.0,
            max_choices_in_scene=0,
            max_transitions_in_scene=0,
            terminal_transition_count=0,
            gated_transition_count=0,
            conditional_transition_count=0,
            item_reward_count=0,
            unique_items_awarded=(),
            unique_items_consumed=(),
            unique_history_records=(),
        )

    scene_count = len(scenes)
    choice_count = 0
    transition_count = 0
    interactive_choice_count = 0
    commands_without_transitions = 0
    max_choices_in_scene = 0
    max_transitions_in_scene = 0
    terminal_transition_count = 0
    gated_transition_count = 0
    conditional_transition_count = 0
    item_reward_count = 0
    awarded_items: set[str] = set()
    consumed_items: set[str] = set()
    history_records: set[str] = set()

    for scene in scenes.values():
        choice_commands = {choice.command for choice in scene.choices}
        choice_count += len(choice_commands)
        max_choices_in_scene = max(max_choices_in_scene, len(choice_commands))

        transitions = scene.transitions
        transition_count += len(transitions)
        max_transitions_in_scene = max(max_transitions_in_scene, len(transitions))
        transition_commands = set(transitions.keys())
        interactive_choice_count += len(choice_commands & transition_commands)
        commands_without_transitions += len(choice_commands - transition_commands)

        for transition in transitions.values():
            if transition.target is None:
                terminal_transition_count += 1
            if transition.requires:
                gated_transition_count += 1
            if transition.narration_overrides:
                conditional_transition_count += 1
            if transition.item:
                item_reward_count += 1
                awarded_items.add(transition.item)
            for item in transition.consumes:
                consumed_items.add(item)
            for record in transition.records:
                history_records.add(record)
            for override in transition.narration_overrides:
                override_records = getattr(override, "records", ())
                for record in override_records:
                    history_records.add(record)

    average_choices_per_scene = _safe_average(choice_count, scene_count)
    average_transitions_per_scene = _safe_average(transition_count, scene_count)

    return AdventureComplexityMetrics(
        scene_count=scene_count,
        choice_count=choice_count,
        transition_count=transition_count,
        interactive_choice_count=interactive_choice_count,
        commands_without_transitions=commands_without_transitions,
        average_choices_per_scene=average_choices_per_scene,
        average_transitions_per_scene=average_transitions_per_scene,
        max_choices_in_scene=max_choices_in_scene,
        max_transitions_in_scene=max_transitions_in_scene,
        terminal_transition_count=terminal_transition_count,
        gated_transition_count=gated_transition_count,
        conditional_transition_count=conditional_transition_count,
        item_reward_count=item_reward_count,
        unique_items_awarded=tuple(sorted(awarded_items)),
        unique_items_consumed=tuple(sorted(consumed_items)),
        unique_history_records=tuple(sorted(history_records)),
    )


def compute_adventure_complexity_from_definitions(
    definitions: Mapping[str, Any],
) -> AdventureComplexityMetrics:
    """Parse a scene definition mapping and compute complexity metrics."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes))


def compute_adventure_complexity_from_file(
    path: str | Path,
) -> AdventureComplexityMetrics:
    """Load scene definitions from ``path`` and compute complexity metrics."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes))


def format_complexity_report(metrics: AdventureComplexityMetrics) -> str:
    """Return a human-friendly report describing the complexity metrics."""

    lines = [
        "Adventure Complexity Metrics",
        "============================",
        f"Scenes: {metrics.scene_count}",
        (
            "Choices: "
            f"{metrics.choice_count} (avg {metrics.average_choices_per_scene:.2f} per scene)"
        ),
        (
            "Interactive choices: "
            f"{metrics.interactive_choice_count}"
            f" (commands without transitions: {metrics.commands_without_transitions})"
        ),
        (
            "Transitions: "
            f"{metrics.transition_count} (avg {metrics.average_transitions_per_scene:.2f} per scene)"
        ),
        f"Max choices in a scene: {metrics.max_choices_in_scene}",
        f"Max transitions in a scene: {metrics.max_transitions_in_scene}",
        f"Terminal transitions (no target): {metrics.terminal_transition_count}",
        f"Gated transitions (require inventory): {metrics.gated_transition_count}",
        f"Transitions with conditional narration: {metrics.conditional_transition_count}",
        f"Transitions awarding items: {metrics.item_reward_count}",
        (
            "Unique items awarded: "
            + (", ".join(metrics.unique_items_awarded) or "(none)")
        ),
        (
            "Unique items consumed: "
            + (", ".join(metrics.unique_items_consumed) or "(none)")
        ),
        (
            "Unique history records: "
            + (", ".join(metrics.unique_history_records) or "(none)")
        ),
    ]
    return "\n".join(lines)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute adventure complexity metrics for a scene definition file."
        )
    )
    parser.add_argument(
        "scene_file",
        nargs="?",
        type=Path,
        help=(
            "Path to a JSON scene definition. Defaults to the bundled demo adventure."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by ``python -m textadventure.analytics``."""

    args = _parse_args(argv)
    if args.scene_file is None:
        from .scripted_story_engine import ScriptedStoryEngine

        scenes = ScriptedStoryEngine().scenes
        metrics = compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes))
    else:
        metrics = compute_adventure_complexity_from_file(args.scene_file)

    report = format_complexity_report(metrics)
    print(report)
    return 0


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    raise SystemExit(main())
