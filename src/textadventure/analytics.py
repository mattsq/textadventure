"""Utilities for analysing scripted adventures and estimating complexity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, cast

from .story_engine import StoryChoice


class _ConditionalNarrationLike(Protocol):
    """Protocol describing the data needed from conditional narration blocks."""

    narration: str
    records: Sequence[str]


class _TransitionLike(Protocol):
    """Protocol describing the fields needed from transition objects."""

    narration: str
    failure_narration: str | None
    target: str | None
    item: str | None
    requires: Sequence[str]
    consumes: Sequence[str]
    records: Sequence[str]
    narration_overrides: Sequence[_ConditionalNarrationLike]


class _SceneLike(Protocol):
    """Protocol describing the subset of scene details required for metrics."""

    description: str
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


@dataclass(frozen=True)
class AdventureReachabilityReport:
    """Summary of which scenes can be visited from a starting location."""

    start_scene: str
    reachable_scenes: tuple[str, ...]
    unreachable_scenes: tuple[str, ...]

    @property
    def reachable_count(self) -> int:
        """Return the number of reachable scenes including the start."""

        return len(self.reachable_scenes)

    @property
    def unreachable_count(self) -> int:
        """Return the number of unreachable scenes."""

        return len(self.unreachable_scenes)

    @property
    def total_scene_count(self) -> int:
        """Return the total number of scenes considered."""

        return self.reachable_count + self.unreachable_count

    @property
    def fully_reachable(self) -> bool:
        """Return ``True`` if every scene can be visited."""

        return self.unreachable_count == 0


@dataclass(frozen=True)
class TextDistributionSummary:
    """Statistical summary describing a collection of text entries."""

    total_entries: int
    empty_entries: int
    total_characters: int
    average_characters: float
    min_characters: int
    max_characters: int
    total_words: int
    average_words: float
    min_words: int
    max_words: int

    @property
    def non_empty_entries(self) -> int:
        """Return the number of entries containing non-whitespace text."""

        return self.total_entries - self.empty_entries


@dataclass(frozen=True)
class AdventureContentDistribution:
    """Summary describing how narrative text is distributed across scenes."""

    scene_descriptions: TextDistributionSummary
    choice_descriptions: TextDistributionSummary
    transition_narrations: TextDistributionSummary
    failure_narrations: TextDistributionSummary
    conditional_narrations: TextDistributionSummary


def _safe_average(total: int, count: int) -> float:
    if count == 0:
        return 0.0
    return total / count


def _normalise_text(value: str) -> str:
    return value.strip()


def _count_words(value: str) -> int:
    stripped = _normalise_text(value)
    if not stripped:
        return 0
    return len(stripped.split())


def _summarise_texts(entries: Sequence[str]) -> TextDistributionSummary:
    total_entries = len(entries)
    if total_entries == 0:
        return TextDistributionSummary(
            total_entries=0,
            empty_entries=0,
            total_characters=0,
            average_characters=0.0,
            min_characters=0,
            max_characters=0,
            total_words=0,
            average_words=0.0,
            min_words=0,
            max_words=0,
        )

    empty_entries = 0
    character_counts: list[int] = []
    word_counts: list[int] = []

    for entry in entries:
        stripped = _normalise_text(entry)
        if not stripped:
            empty_entries += 1
        character_count = len(stripped)
        word_count = _count_words(stripped)
        character_counts.append(character_count)
        word_counts.append(word_count)

    total_characters = sum(character_counts)
    total_words = sum(word_counts)
    average_characters = total_characters / total_entries
    average_words = total_words / total_entries

    return TextDistributionSummary(
        total_entries=total_entries,
        empty_entries=empty_entries,
        total_characters=total_characters,
        average_characters=average_characters,
        min_characters=min(character_counts),
        max_characters=max(character_counts),
        total_words=total_words,
        average_words=average_words,
        min_words=min(word_counts),
        max_words=max(word_counts),
    )


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


def compute_adventure_content_distribution(
    scenes: Mapping[str, _SceneLike],
) -> AdventureContentDistribution:
    """Summarise how narrative text is distributed across scenes."""

    scene_descriptions = [scene.description for scene in scenes.values()]
    choice_descriptions = [
        choice.description for scene in scenes.values() for choice in scene.choices
    ]
    transition_narrations = [
        transition.narration
        for scene in scenes.values()
        for transition in scene.transitions.values()
    ]
    failure_narrations = [
        transition.failure_narration
        for scene in scenes.values()
        for transition in scene.transitions.values()
        if transition.failure_narration is not None
    ]
    conditional_narrations = [
        override.narration
        for scene in scenes.values()
        for transition in scene.transitions.values()
        for override in transition.narration_overrides
    ]

    return AdventureContentDistribution(
        scene_descriptions=_summarise_texts(scene_descriptions),
        choice_descriptions=_summarise_texts(choice_descriptions),
        transition_narrations=_summarise_texts(transition_narrations),
        failure_narrations=_summarise_texts(failure_narrations),
        conditional_narrations=_summarise_texts(conditional_narrations),
    )


def compute_adventure_content_distribution_from_definitions(
    definitions: Mapping[str, Any],
) -> AdventureContentDistribution:
    """Parse scene definitions and summarise the narrative content distribution."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return compute_adventure_content_distribution(
        cast(Mapping[str, _SceneLike], scenes)
    )


def compute_adventure_content_distribution_from_file(
    path: str | Path,
) -> AdventureContentDistribution:
    """Load scene definitions from ``path`` and summarise the content distribution."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return compute_adventure_content_distribution(
        cast(Mapping[str, _SceneLike], scenes)
    )


def compute_scene_reachability(
    scenes: Mapping[str, _SceneLike],
    *,
    start_scene: str = "starting-area",
) -> AdventureReachabilityReport:
    """Determine which scenes are reachable from ``start_scene``.

    The analysis walks the directed graph formed by transition targets while
    ignoring inventory/history requirements. This approximates structural
    reachability and is sufficient for spotting orphaned scenes.
    """

    if start_scene not in scenes:
        raise ValueError(f"Start scene '{start_scene}' is not defined.")

    visited: set[str] = set()
    frontier = [start_scene]

    while frontier:
        current = frontier.pop()
        if current in visited:
            continue

        visited.add(current)
        transitions = scenes[current].transitions
        for transition in transitions.values():
            target = transition.target
            if target is None or target in visited:
                continue
            if target in scenes:
                frontier.append(target)

    reachable = tuple(sorted(visited))
    unreachable = tuple(sorted(scene for scene in scenes if scene not in visited))

    return AdventureReachabilityReport(
        start_scene=start_scene,
        reachable_scenes=reachable,
        unreachable_scenes=unreachable,
    )


def compute_scene_reachability_from_definitions(
    definitions: Mapping[str, Any],
    *,
    start_scene: str = "starting-area",
) -> AdventureReachabilityReport:
    """Parse a scene definition mapping and compute reachability statistics."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return compute_scene_reachability(
        cast(Mapping[str, _SceneLike], scenes), start_scene=start_scene
    )


def compute_scene_reachability_from_file(
    path: str | Path,
    *,
    start_scene: str = "starting-area",
) -> AdventureReachabilityReport:
    """Load scene definitions from ``path`` and compute reachability statistics."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return compute_scene_reachability(
        cast(Mapping[str, _SceneLike], scenes), start_scene=start_scene
    )


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


def format_reachability_report(report: AdventureReachabilityReport) -> str:
    """Return a human-friendly report describing scene reachability."""

    lines = [
        "Adventure Reachability",
        "======================",
        f"Start scene: {report.start_scene}",
        ("Reachable scenes: " f"{report.reachable_count} / {report.total_scene_count}"),
    ]

    if report.reachable_scenes:
        lines.append(
            "Reachable scene list: " + (", ".join(report.reachable_scenes) or "(none)")
        )

    if report.unreachable_scenes:
        lines.append("Unreachable scenes detected:")
        lines.extend(f"- {scene}" for scene in report.unreachable_scenes)
    else:
        lines.append("All scenes are reachable from the starting location.")

    return "\n".join(lines)


def _format_distribution_section(
    title: str, summary: TextDistributionSummary
) -> list[str]:
    return [
        f"{title}:",
        f"  Total entries: {summary.total_entries}",
        f"  Non-empty entries: {summary.non_empty_entries}",
        (
            "  Words: "
            f"{summary.total_words} (avg {summary.average_words:.2f}, "
            f"min {summary.min_words}, max {summary.max_words})"
        ),
        (
            "  Characters: "
            f"{summary.total_characters} (avg {summary.average_characters:.2f}, "
            f"min {summary.min_characters}, max {summary.max_characters})"
        ),
    ]


def format_content_distribution_report(
    distribution: AdventureContentDistribution,
) -> str:
    """Return a human-friendly report summarising content distribution."""

    lines = [
        "Adventure Content Distribution",
        "==============================",
    ]

    lines.extend(
        _format_distribution_section(
            "Scene descriptions", distribution.scene_descriptions
        )
    )
    lines.extend(
        _format_distribution_section(
            "Choice descriptions", distribution.choice_descriptions
        )
    )
    lines.extend(
        _format_distribution_section(
            "Transition narrations", distribution.transition_narrations
        )
    )
    lines.extend(
        _format_distribution_section(
            "Failure narrations", distribution.failure_narrations
        )
    )
    lines.extend(
        _format_distribution_section(
            "Conditional narrations", distribution.conditional_narrations
        )
    )

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
    parser.add_argument(
        "--start-scene",
        default="starting-area",
        help=(
            "Scene identifier to treat as the starting point when computing "
            "reachability."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point used by ``python -m textadventure.analytics``."""

    args = _parse_args(argv)
    if args.scene_file is None:
        from .scripted_story_engine import ScriptedStoryEngine

        scenes = ScriptedStoryEngine().scenes
    else:
        from .scripted_story_engine import load_scenes_from_file

        scenes = load_scenes_from_file(args.scene_file)

    scene_mapping = cast(Mapping[str, _SceneLike], scenes)
    metrics = compute_adventure_complexity(scene_mapping)
    content_distribution = compute_adventure_content_distribution(scene_mapping)
    reachability = compute_scene_reachability(
        scene_mapping, start_scene=args.start_scene
    )

    report = format_complexity_report(metrics)
    distribution_report = format_content_distribution_report(content_distribution)
    reachability_report = format_reachability_report(reachability)
    print(report)
    print()
    print(distribution_report)
    print()
    print(reachability_report)
    return 0


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    raise SystemExit(main())
