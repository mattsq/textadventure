"""Utilities for analysing scripted adventures and estimating complexity."""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, cast

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


@dataclass(frozen=True)
class AdventureQualityReport:
    """Summary describing potential content quality issues."""

    scenes_missing_description: tuple[str, ...]
    choices_missing_description: tuple[tuple[str, str], ...]
    transitions_missing_narration: tuple[tuple[str, str], ...]
    gated_transitions_missing_failure: tuple[tuple[str, str], ...]
    conditional_overrides_missing_narration: tuple[tuple[str, str, int], ...]
    transitions_with_unknown_targets: tuple[tuple[str, str, str], ...]

    @property
    def issue_count(self) -> int:
        """Return the total number of detected issues across all categories."""

        return sum(
            (
                len(self.scenes_missing_description),
                len(self.choices_missing_description),
                len(self.transitions_missing_narration),
                len(self.gated_transitions_missing_failure),
                len(self.conditional_overrides_missing_narration),
                len(self.transitions_with_unknown_targets),
            )
        )

    @property
    def has_issues(self) -> bool:
        """Return ``True`` when any potential quality issue was detected."""

        return self.issue_count > 0


@dataclass(frozen=True)
class ItemSource:
    """Location describing where an item can be acquired."""

    scene: str
    command: str


@dataclass(frozen=True)
class ItemRequirement:
    """Location describing where an item is required but not consumed."""

    scene: str
    command: str


@dataclass(frozen=True)
class ItemConsumption:
    """Location describing where an item is consumed and removed."""

    scene: str
    command: str


@dataclass(frozen=True)
class ItemFlowDetails:
    """Summary of how a specific item flows through an adventure."""

    item: str
    sources: tuple[ItemSource, ...]
    requirements: tuple[ItemRequirement, ...]
    consumptions: tuple[ItemConsumption, ...]

    @property
    def is_orphaned(self) -> bool:
        """Return ``True`` when the item can be acquired but never used."""

        return bool(self.sources) and not (self.requirements or self.consumptions)

    @property
    def is_missing_source(self) -> bool:
        """Return ``True`` when the item is required or consumed but never awarded."""

        return bool((not self.sources) and (self.requirements or self.consumptions))

    @property
    def total_sources(self) -> int:
        """Return the number of award locations for the item."""

        return len(self.sources)

    @property
    def total_requirements(self) -> int:
        """Return the number of transitions that require the item."""

        return len(self.requirements)

    @property
    def total_consumptions(self) -> int:
        """Return the number of transitions that consume the item."""

        return len(self.consumptions)

    @property
    def net_consumable_balance(self) -> int:
        """Return the difference between award and consumption events."""

        return self.total_sources - self.total_consumptions

    @property
    def has_surplus_awards(self) -> bool:
        """Return ``True`` when the item can be acquired more often than consumed."""

        return self.total_consumptions > 0 and self.net_consumable_balance > 0

    @property
    def has_consumption_deficit(self) -> bool:
        """Return ``True`` when the item is consumed more often than it can be acquired."""

        return self.total_consumptions > self.total_sources


@dataclass(frozen=True)
class ItemFlowReport:
    """Aggregate summary describing how items circulate throughout an adventure."""

    items: tuple[ItemFlowDetails, ...]

    @property
    def orphaned_items(self) -> tuple[str, ...]:
        """Return item identifiers that can be acquired but are never referenced."""

        return tuple(detail.item for detail in self.items if detail.is_orphaned)

    @property
    def items_missing_sources(self) -> tuple[str, ...]:
        """Return item identifiers that are required or consumed without a source."""

        return tuple(detail.item for detail in self.items if detail.is_missing_source)

    @property
    def items_with_surplus_awards(self) -> tuple[str, ...]:
        """Return item identifiers that are awarded more times than they are consumed."""

        return tuple(detail.item for detail in self.items if detail.has_surplus_awards)

    @property
    def items_with_consumption_deficit(self) -> tuple[str, ...]:
        """Return item identifiers that are consumed more times than they are awarded."""

        return tuple(
            detail.item for detail in self.items if detail.has_consumption_deficit
        )


@dataclass(frozen=True)
class AdventureABMetricDelta:
    """Difference between numeric metrics for two narrative variants."""

    metric: str
    variant_a_value: float
    variant_b_value: float
    absolute_difference: float
    relative_difference: float | None

    @property
    def variant_b_is_higher(self) -> bool:
        """Return ``True`` when variant B increased the metric."""

        return self.absolute_difference > 0

    @property
    def variant_b_is_lower(self) -> bool:
        """Return ``True`` when variant B decreased the metric."""

        return self.absolute_difference < 0


@dataclass(frozen=True)
class AdventureABCollectionDifference:
    """Difference summary describing added/removed identifiers between variants."""

    added: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def has_changes(self) -> bool:
        """Return ``True`` when either variant introduced or removed identifiers."""

        return bool(self.added or self.removed)


@dataclass(frozen=True)
class AdventureABTestReport:
    """Aggregate report describing how two narrative variants compare."""

    variant_a_name: str
    variant_b_name: str
    metric_deltas: tuple[AdventureABMetricDelta, ...]
    awarded_item_changes: AdventureABCollectionDifference
    consumed_item_changes: AdventureABCollectionDifference
    history_record_changes: AdventureABCollectionDifference

    @property
    def changed_metrics(self) -> tuple[AdventureABMetricDelta, ...]:
        """Return metric deltas where the variants differ."""

        return tuple(
            delta for delta in self.metric_deltas if delta.absolute_difference != 0
        )

    @property
    def unchanged_metrics(self) -> tuple[AdventureABMetricDelta, ...]:
        """Return metric deltas where the variants match."""

        return tuple(
            delta for delta in self.metric_deltas if delta.absolute_difference == 0
        )


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


_COMPLEXITY_METRIC_ACCESSORS: tuple[
    tuple[str, Callable[[AdventureComplexityMetrics], float]], ...
] = (
    ("scene_count", lambda metrics: float(metrics.scene_count)),
    ("choice_count", lambda metrics: float(metrics.choice_count)),
    ("transition_count", lambda metrics: float(metrics.transition_count)),
    (
        "interactive_choice_count",
        lambda metrics: float(metrics.interactive_choice_count),
    ),
    (
        "commands_without_transitions",
        lambda metrics: float(metrics.commands_without_transitions),
    ),
    (
        "average_choices_per_scene",
        lambda metrics: float(metrics.average_choices_per_scene),
    ),
    (
        "average_transitions_per_scene",
        lambda metrics: float(metrics.average_transitions_per_scene),
    ),
    ("max_choices_in_scene", lambda metrics: float(metrics.max_choices_in_scene)),
    (
        "max_transitions_in_scene",
        lambda metrics: float(metrics.max_transitions_in_scene),
    ),
    (
        "terminal_transition_count",
        lambda metrics: float(metrics.terminal_transition_count),
    ),
    (
        "gated_transition_count",
        lambda metrics: float(metrics.gated_transition_count),
    ),
    (
        "conditional_transition_count",
        lambda metrics: float(metrics.conditional_transition_count),
    ),
    ("item_reward_count", lambda metrics: float(metrics.item_reward_count)),
    (
        "unique_item_reward_count",
        lambda metrics: float(metrics.unique_item_reward_count),
    ),
    (
        "unique_item_consumption_count",
        lambda metrics: float(metrics.unique_item_consumption_count),
    ),
    (
        "unique_history_record_count",
        lambda metrics: float(metrics.unique_history_record_count),
    ),
)


def _compute_relative_delta(old: float, new: float) -> float | None:
    if old == 0.0:
        if new == 0.0:
            return 0.0
        return None
    return (new - old) / old


def _compare_identifier_collections(
    identifiers_a: Sequence[str],
    identifiers_b: Sequence[str],
) -> AdventureABCollectionDifference:
    set_a = set(identifiers_a)
    set_b = set(identifiers_b)
    added = tuple(sorted(set_b - set_a))
    removed = tuple(sorted(set_a - set_b))
    return AdventureABCollectionDifference(added=added, removed=removed)


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


def assess_adventure_quality(
    scenes: Mapping[str, _SceneLike],
) -> AdventureQualityReport:
    """Perform heuristic checks to highlight possible content issues."""

    scenes_missing_description: list[str] = []
    choices_missing_description: list[tuple[str, str]] = []
    transitions_missing_narration: list[tuple[str, str]] = []
    gated_transitions_missing_failure: list[tuple[str, str]] = []
    conditional_overrides_missing_narration: list[tuple[str, str, int]] = []
    transitions_with_unknown_targets: list[tuple[str, str, str]] = []

    defined_scene_ids = set(scenes)

    for scene_id, scene in scenes.items():
        if not _normalise_text(scene.description):
            scenes_missing_description.append(scene_id)

        for choice in scene.choices:
            if not _normalise_text(choice.description):
                choices_missing_description.append((scene_id, choice.command))

        for command, transition in scene.transitions.items():
            if not _normalise_text(transition.narration):
                transitions_missing_narration.append((scene_id, command))

            target = transition.target
            if target and target not in defined_scene_ids:
                transitions_with_unknown_targets.append((scene_id, command, target))

            if (transition.requires or transition.consumes) and (
                transition.failure_narration is None
                or not _normalise_text(transition.failure_narration)
            ):
                gated_transitions_missing_failure.append((scene_id, command))

            for index, override in enumerate(transition.narration_overrides):
                if not _normalise_text(override.narration):
                    conditional_overrides_missing_narration.append(
                        (scene_id, command, index)
                    )

    return AdventureQualityReport(
        scenes_missing_description=tuple(sorted(scenes_missing_description)),
        choices_missing_description=tuple(sorted(choices_missing_description)),
        transitions_missing_narration=tuple(sorted(transitions_missing_narration)),
        gated_transitions_missing_failure=tuple(
            sorted(gated_transitions_missing_failure)
        ),
        conditional_overrides_missing_narration=tuple(
            sorted(conditional_overrides_missing_narration)
        ),
        transitions_with_unknown_targets=tuple(
            sorted(transitions_with_unknown_targets)
        ),
    )


def assess_adventure_quality_from_definitions(
    definitions: Mapping[str, Any],
) -> AdventureQualityReport:
    """Parse scene definitions and perform quality checks."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return assess_adventure_quality(cast(Mapping[str, _SceneLike], scenes))


def assess_adventure_quality_from_file(
    path: str | Path,
) -> AdventureQualityReport:
    """Load scene definitions from ``path`` and perform quality checks."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return assess_adventure_quality(cast(Mapping[str, _SceneLike], scenes))


def analyse_item_flow(scenes: Mapping[str, _SceneLike]) -> ItemFlowReport:
    """Analyse where items originate and how they are referenced."""

    sources_by_item: defaultdict[str, list[ItemSource]] = defaultdict(list)
    requirements_by_item: defaultdict[str, list[ItemRequirement]] = defaultdict(list)
    consumptions_by_item: defaultdict[str, list[ItemConsumption]] = defaultdict(list)

    for scene_id, scene in scenes.items():
        for command, transition in scene.transitions.items():
            if transition.item:
                sources_by_item[transition.item].append(
                    ItemSource(scene=scene_id, command=command)
                )
            for requirement in transition.requires:
                requirements_by_item[requirement].append(
                    ItemRequirement(scene=scene_id, command=command)
                )
            for consumed in transition.consumes:
                consumptions_by_item[consumed].append(
                    ItemConsumption(scene=scene_id, command=command)
                )

    all_items = sorted(
        {
            *sources_by_item.keys(),
            *requirements_by_item.keys(),
            *consumptions_by_item.keys(),
        }
    )

    def _sorted_sources(item: str) -> tuple[ItemSource, ...]:
        events = sources_by_item.get(item, [])
        return tuple(sorted(events, key=lambda event: (event.scene, event.command)))

    def _sorted_requirements(item: str) -> tuple[ItemRequirement, ...]:
        events = requirements_by_item.get(item, [])
        return tuple(sorted(events, key=lambda event: (event.scene, event.command)))

    def _sorted_consumptions(item: str) -> tuple[ItemConsumption, ...]:
        events = consumptions_by_item.get(item, [])
        return tuple(sorted(events, key=lambda event: (event.scene, event.command)))

    details = [
        ItemFlowDetails(
            item=item,
            sources=_sorted_sources(item),
            requirements=_sorted_requirements(item),
            consumptions=_sorted_consumptions(item),
        )
        for item in all_items
    ]

    return ItemFlowReport(items=tuple(details))


def analyse_item_flow_from_definitions(
    definitions: Mapping[str, Any],
) -> ItemFlowReport:
    """Parse scene definitions and analyse item flow."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return analyse_item_flow(cast(Mapping[str, _SceneLike], scenes))


def analyse_item_flow_from_file(path: str | Path) -> ItemFlowReport:
    """Load scene definitions from ``path`` and analyse item flow."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return analyse_item_flow(cast(Mapping[str, _SceneLike], scenes))


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


def compare_adventure_variants(
    metrics_a: AdventureComplexityMetrics,
    metrics_b: AdventureComplexityMetrics,
    *,
    variant_a_name: str = "Variant A",
    variant_b_name: str = "Variant B",
) -> AdventureABTestReport:
    """Compare two adventures and summarise how their metrics differ."""

    metric_deltas: list[AdventureABMetricDelta] = []
    for metric_name, accessor in _COMPLEXITY_METRIC_ACCESSORS:
        a_value = accessor(metrics_a)
        b_value = accessor(metrics_b)
        delta = b_value - a_value
        relative = _compute_relative_delta(a_value, b_value)
        metric_deltas.append(
            AdventureABMetricDelta(
                metric=metric_name,
                variant_a_value=a_value,
                variant_b_value=b_value,
                absolute_difference=delta,
                relative_difference=relative,
            )
        )

    awarded_diff = _compare_identifier_collections(
        metrics_a.unique_items_awarded, metrics_b.unique_items_awarded
    )
    consumed_diff = _compare_identifier_collections(
        metrics_a.unique_items_consumed, metrics_b.unique_items_consumed
    )
    history_diff = _compare_identifier_collections(
        metrics_a.unique_history_records, metrics_b.unique_history_records
    )

    return AdventureABTestReport(
        variant_a_name=variant_a_name,
        variant_b_name=variant_b_name,
        metric_deltas=tuple(metric_deltas),
        awarded_item_changes=awarded_diff,
        consumed_item_changes=consumed_diff,
        history_record_changes=history_diff,
    )


def compare_adventure_variants_from_definitions(
    definitions_a: Mapping[str, Any],
    definitions_b: Mapping[str, Any],
    *,
    variant_a_name: str = "Variant A",
    variant_b_name: str = "Variant B",
) -> AdventureABTestReport:
    """Parse scene definitions and compare the resulting adventure variants."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes_a = load_scenes_from_mapping(definitions_a)
    scenes_b = load_scenes_from_mapping(definitions_b)
    metrics_a = compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes_a))
    metrics_b = compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes_b))
    return compare_adventure_variants(
        metrics_a,
        metrics_b,
        variant_a_name=variant_a_name,
        variant_b_name=variant_b_name,
    )


def compare_adventure_variants_from_file(
    path_a: str | Path,
    path_b: str | Path,
    *,
    variant_a_name: str = "Variant A",
    variant_b_name: str = "Variant B",
) -> AdventureABTestReport:
    """Load scene files and compare the resulting adventure variants."""

    from .scripted_story_engine import load_scenes_from_file

    scenes_a = load_scenes_from_file(path_a)
    scenes_b = load_scenes_from_file(path_b)
    metrics_a = compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes_a))
    metrics_b = compute_adventure_complexity(cast(Mapping[str, _SceneLike], scenes_b))
    return compare_adventure_variants(
        metrics_a,
        metrics_b,
        variant_a_name=variant_a_name,
        variant_b_name=variant_b_name,
    )


def format_ab_test_report(
    report: AdventureABTestReport, *, include_zero_deltas: bool = False
) -> str:
    """Return a human-friendly summary comparing two adventure variants."""

    title = f"A/B Test Comparison: {report.variant_a_name} vs {report.variant_b_name}"
    lines = [title, "=" * len(title), ""]

    metric_lines = []
    for delta in report.metric_deltas:
        if not include_zero_deltas and delta.absolute_difference == 0:
            continue

        change_details = f"Δ {delta.absolute_difference:+g}"
        if delta.relative_difference is not None:
            change_details += f" ({delta.relative_difference * 100:+.1f}%)"

        metric_lines.append(
            (
                f"- {delta.metric}: {report.variant_a_name} "
                f"{delta.variant_a_value:g} -> {report.variant_b_name} "
                f"{delta.variant_b_value:g} [{change_details}]"
            )
        )

    lines.append("Metric changes:")
    if metric_lines:
        lines.extend(metric_lines)
    else:
        lines.append("- No numeric differences detected.")

    collection_sections = [
        ("Unique items awarded", report.awarded_item_changes),
        ("Unique items consumed", report.consumed_item_changes),
        ("History records", report.history_record_changes),
    ]

    for label, difference in collection_sections:
        lines.append("")
        lines.append(f"{label}:")
        if difference.added:
            lines.append(f"- Added in {report.variant_b_name}:")
            lines.extend(f"  - {item}" for item in difference.added)
        if difference.removed:
            lines.append(f"- Removed in {report.variant_b_name}:")
            lines.extend(f"  - {item}" for item in difference.removed)
        if not difference.has_changes:
            lines.append("- No changes")

    return "\n".join(lines)


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


def format_item_flow_report(report: ItemFlowReport) -> str:
    """Return a human-friendly report describing item sources and usage."""

    lines = ["Adventure Item Flow", "==================="]

    if not report.items:
        lines.append("No items are awarded, required, or consumed in this adventure.")
        return "\n".join(lines)

    for detail in report.items:
        lines.append(f"Item: {detail.item}")
        if detail.sources:
            lines.append("  Sources:")
            lines.extend(
                f"    - {source.scene} :: {source.command}" for source in detail.sources
            )
        else:
            lines.append("  Sources: (none)")

        if detail.requirements:
            lines.append("  Required by:")
            lines.extend(
                f"    - {requirement.scene} :: {requirement.command}"
                for requirement in detail.requirements
            )
        else:
            lines.append("  Required by: (none)")

        if detail.consumptions:
            lines.append("  Consumed by:")
            lines.extend(
                f"    - {consumption.scene} :: {consumption.command}"
                for consumption in detail.consumptions
            )
        else:
            lines.append("  Consumed by: (none)")

        lines.append("")

    if lines[-1] == "":
        lines.pop()

    summary_sections: list[tuple[str, tuple[str, ...]]] = []

    if report.orphaned_items:
        summary_sections.append(
            ("Items awarded but never used:", report.orphaned_items)
        )

    if report.items_missing_sources:
        summary_sections.append(
            ("Items referenced without a source:", report.items_missing_sources)
        )

    if report.items_with_surplus_awards:
        summary_sections.append(
            (
                "Items awarded more times than they are consumed (potential surplus):",
                report.items_with_surplus_awards,
            )
        )

    if report.items_with_consumption_deficit:
        summary_sections.append(
            (
                "Items consumed more times than they are awarded (potential deficit):",
                report.items_with_consumption_deficit,
            )
        )

    if summary_sections:
        lines.append("")
        for title, items in summary_sections:
            lines.append(title)
            lines.extend(f"- {item}" for item in items)
    else:
        lines.append("")
        lines.append(
            "All awarded items are referenced, every requirement has a source, "
            "and consumable items have balanced awards."
        )

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


def format_quality_report(report: AdventureQualityReport) -> str:
    """Return a human-friendly report highlighting potential issues."""

    lines = [
        "Adventure Quality Assessment",
        "============================",
        f"Total issues detected: {report.issue_count}",
    ]

    if report.scenes_missing_description:
        lines.append("Scenes missing descriptions:")
        lines.extend(f"- {scene}" for scene in report.scenes_missing_description)

    if report.choices_missing_description:
        lines.append("Choices missing descriptions:")
        lines.extend(
            f"- {scene} :: {command}"
            for scene, command in report.choices_missing_description
        )

    if report.transitions_missing_narration:
        lines.append("Transitions missing narration:")
        lines.extend(
            f"- {scene} :: {command}"
            for scene, command in report.transitions_missing_narration
        )

    if report.gated_transitions_missing_failure:
        lines.append("Gated transitions missing failure narration:")
        lines.extend(
            f"- {scene} :: {command}"
            for scene, command in report.gated_transitions_missing_failure
        )

    if report.conditional_overrides_missing_narration:
        lines.append("Conditional overrides missing narration:")
        lines.extend(
            f"- {scene} :: {command} (override #{index + 1})"
            for scene, command, index in report.conditional_overrides_missing_narration
        )

    if report.transitions_with_unknown_targets:
        lines.append("Transitions targeting unknown scenes:")
        lines.extend(
            f"- {scene} :: {command} -> {target}"
            for scene, command, target in report.transitions_with_unknown_targets
        )

    if len(lines) == 3:
        lines.append("No quality issues detected.")

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
    quality = assess_adventure_quality(scene_mapping)
    item_flow = analyse_item_flow(scene_mapping)

    report = format_complexity_report(metrics)
    distribution_report = format_content_distribution_report(content_distribution)
    reachability_report = format_reachability_report(reachability)
    item_flow_report = format_item_flow_report(item_flow)
    quality_report = format_quality_report(quality)
    print(report)
    print()
    print(distribution_report)
    print()
    print(reachability_report)
    print()
    print(item_flow_report)
    print()
    print(quality_report)
    return 0


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    raise SystemExit(main())
