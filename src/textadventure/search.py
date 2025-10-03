"""Utilities for searching scripted scene text content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Collection,
    Iterable,
    Mapping,
    MutableMapping,
    Protocol,
    Sequence,
    Tuple,
    Literal,
    cast,
)


FieldType = Literal[
    "scene_description",
    "choice_description",
    "transition_narration",
    "transition_failure_narration",
    "override_narration",
]


ReferenceCategory = Literal["scene", "item", "history"]


ReferenceType = Literal[
    "transition_target",
    "transition_item_award",
    "transition_item_requirement",
    "transition_item_consumption",
    "override_item_requirement_all",
    "override_item_requirement_any",
    "override_item_forbidden",
    "transition_history_record",
    "override_history_record",
    "override_history_requirement_all",
    "override_history_requirement_any",
    "override_history_forbidden",
]


_REFERENCE_TYPE_TO_CATEGORY: Mapping[ReferenceType, ReferenceCategory] = {
    "transition_target": "scene",
    "transition_item_award": "item",
    "transition_item_requirement": "item",
    "transition_item_consumption": "item",
    "override_item_requirement_all": "item",
    "override_item_requirement_any": "item",
    "override_item_forbidden": "item",
    "transition_history_record": "history",
    "override_history_record": "history",
    "override_history_requirement_all": "history",
    "override_history_requirement_any": "history",
    "override_history_forbidden": "history",
}

_REFERENCE_CATEGORIES: frozenset[ReferenceCategory] = frozenset(
    _REFERENCE_TYPE_TO_CATEGORY.values()
)
_REFERENCE_TYPES: frozenset[ReferenceType] = frozenset(
    _REFERENCE_TYPE_TO_CATEGORY.keys()
)


class _ChoiceLike(Protocol):
    command: str
    description: str


class _OverrideLike(Protocol):
    narration: str
    records: Sequence[str]
    requires_history_all: Sequence[str]
    requires_history_any: Sequence[str]
    forbids_history_any: Sequence[str]
    requires_inventory_all: Sequence[str]
    requires_inventory_any: Sequence[str]
    forbids_inventory_any: Sequence[str]


class _TransitionLike(Protocol):
    narration: str
    failure_narration: str | None
    target: str | None
    item: str | None
    requires: Sequence[str]
    consumes: Sequence[str]
    records: Sequence[str]
    narration_overrides: Sequence[_OverrideLike]


class _SceneLike(Protocol):
    description: str
    choices: Sequence[_ChoiceLike]
    transitions: Mapping[str, _TransitionLike]


@dataclass(frozen=True)
class TextSpan:
    """Range describing where a search query matched inside a string."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < 0:
            raise ValueError("Span indices must be non-negative")
        if self.end <= self.start:
            raise ValueError("Span end must be greater than start")


@dataclass(frozen=True)
class FieldMatch:
    """Record describing where a query matched inside a specific field."""

    field_type: FieldType
    path: str
    text: str
    spans: Tuple[TextSpan, ...]

    @property
    def match_count(self) -> int:
        """Return how many times the query matched within this field."""

        return len(self.spans)


@dataclass(frozen=True)
class SceneSearchResult:
    """Aggregated matches for a single scene."""

    scene_id: str
    matches: Tuple[FieldMatch, ...]

    @property
    def match_count(self) -> int:
        """Return how many total matches were found for the scene."""

        return sum(match.match_count for match in self.matches)


@dataclass(frozen=True)
class SearchResults:
    """Collection of matches for a search query."""

    query: str
    results: Tuple[SceneSearchResult, ...]

    @property
    def total_results(self) -> int:
        """Return how many scenes contained at least one match."""

        return len(self.results)

    @property
    def total_match_count(self) -> int:
        """Return the total number of matches across all scenes."""

        return sum(result.match_count for result in self.results)


@dataclass(frozen=True)
class FieldReplacement:
    """Record describing text replacements applied within a field."""

    field_type: FieldType
    path: str
    original_text: str
    updated_text: str
    spans: Tuple[TextSpan, ...]

    @property
    def replacement_count(self) -> int:
        """Return how many replacements were applied within this field."""

        return len(self.spans)


@dataclass(frozen=True)
class SceneReplacementResult:
    """Aggregated replacements for a single scene."""

    scene_id: str
    replacements: Tuple[FieldReplacement, ...]

    @property
    def replacement_count(self) -> int:
        """Return the total number of replacements across the scene."""

        return sum(replacement.replacement_count for replacement in self.replacements)


@dataclass(frozen=True)
class ReplacementResults:
    """Collection of replacements applied for a query."""

    query: str
    replacement_text: str
    results: Tuple[SceneReplacementResult, ...]

    @property
    def total_results(self) -> int:
        """Return how many scenes were modified by the replacement."""

        return len(self.results)

    @property
    def total_replacement_count(self) -> int:
        """Return the total number of replacements across all scenes."""

        return sum(result.replacement_count for result in self.results)


@dataclass(frozen=True)
class ReferenceMatch:
    """Structured description of where an identifier is referenced."""

    category: ReferenceCategory
    reference_type: ReferenceType
    path: str
    value: str


@dataclass(frozen=True)
class SceneReferenceResult:
    """Aggregated reference matches for a single scene."""

    scene_id: str
    matches: Tuple[ReferenceMatch, ...]

    @property
    def match_count(self) -> int:
        """Return how many references were found within the scene."""

        return len(self.matches)


@dataclass(frozen=True)
class ReferenceResults:
    """Collection of reference matches for an identifier query."""

    identifier: str
    results: Tuple[SceneReferenceResult, ...]

    @property
    def total_results(self) -> int:
        """Return how many scenes include at least one reference."""

        return len(self.results)

    @property
    def total_match_count(self) -> int:
        """Return the total number of references across all scenes."""

        return sum(result.match_count for result in self.results)


def search_scene_text(
    scenes: Mapping[str, _SceneLike],
    query: str,
    *,
    field_types: Collection[FieldType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> SearchResults:
    """Search narrative text fields across ``scenes`` for ``query``.

    The search inspects scene descriptions, choice descriptions, transition
    narrations, failure narrations, and conditional override narrations.
    Matching is case-insensitive and returns positional spans for callers that
    wish to highlight hits. Leading and trailing whitespace is ignored.

    Optional ``field_types`` can restrict which narrative fields contribute to
    the result set, while ``allowed_scene_ids`` limits which scenes are
    considered during the search.
    """

    normalised_query = query.strip()
    if not normalised_query:
        raise ValueError("Search query must not be empty.")

    pattern = re.compile(re.escape(normalised_query), re.IGNORECASE)
    results: list[SceneSearchResult] = []
    allowed_fields = set(field_types) if field_types is not None else None
    allowed_scenes = set(allowed_scene_ids) if allowed_scene_ids is not None else None

    for scene_id in sorted(scenes.keys()):
        if allowed_scenes is not None and scene_id not in allowed_scenes:
            continue
        scene = scenes[scene_id]
        matches: list[FieldMatch] = []

        matches.extend(
            _iter_field_matches(
                pattern,
                field_type="scene_description",
                path="description",
                text=scene.description,
            )
        )

        for choice in scene.choices:
            matches.extend(
                _iter_field_matches(
                    pattern,
                    field_type="choice_description",
                    path=f"choices.{choice.command}.description",
                    text=choice.description,
                )
            )

        for command, transition in scene.transitions.items():
            matches.extend(
                _iter_field_matches(
                    pattern,
                    field_type="transition_narration",
                    path=f"transitions.{command}.narration",
                    text=transition.narration,
                )
            )
            if transition.failure_narration is not None:
                matches.extend(
                    _iter_field_matches(
                        pattern,
                        field_type="transition_failure_narration",
                        path=f"transitions.{command}.failure_narration",
                        text=transition.failure_narration,
                    )
                )
            for index, override in enumerate(transition.narration_overrides):
                matches.extend(
                    _iter_field_matches(
                        pattern,
                        field_type="override_narration",
                        path=(
                            f"transitions.{command}."
                            f"narration_overrides[{index}].narration"
                        ),
                        text=override.narration,
                    )
                )

        if matches:
            if allowed_fields is not None:
                matches = [
                    match for match in matches if match.field_type in allowed_fields
                ]

            matches.sort(key=lambda match: (match.field_type, match.path))
            if matches:
                results.append(
                    SceneSearchResult(scene_id=scene_id, matches=tuple(matches))
                )

    return SearchResults(query=normalised_query, results=tuple(results))


def search_scene_text_from_definitions(
    definitions: Mapping[str, Any],
    query: str,
    *,
    field_types: Collection[FieldType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> SearchResults:
    """Parse scene definitions and search their text content."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return search_scene_text(
        cast(Mapping[str, _SceneLike], scenes),
        query,
        field_types=field_types,
        allowed_scene_ids=allowed_scene_ids,
    )


def search_scene_text_from_file(
    path: str | Path,
    query: str,
    *,
    field_types: Collection[FieldType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> SearchResults:
    """Load scene definitions from ``path`` and search their text content."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return search_scene_text(
        cast(Mapping[str, _SceneLike], scenes),
        query,
        field_types=field_types,
        allowed_scene_ids=allowed_scene_ids,
    )


def replace_scene_text_in_definitions(
    definitions: MutableMapping[str, Any],
    query: str,
    replacement: str,
    *,
    field_types: Collection[FieldType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> ReplacementResults:
    """Replace occurrences of ``query`` within scene definition text fields.

    The operation mutates ``definitions`` in-place, substituting case-insensitive
    matches of ``query`` with ``replacement`` across the same narrative fields
    inspected by :func:`search_scene_text`.
    """

    normalised_query = query.strip()
    if not normalised_query:
        raise ValueError("Search query must not be empty.")

    pattern = re.compile(re.escape(normalised_query), re.IGNORECASE)
    allowed_fields = set(field_types) if field_types is not None else None
    allowed_scenes = set(allowed_scene_ids) if allowed_scene_ids is not None else None
    scene_results: list[SceneReplacementResult] = []

    for scene_id in sorted(definitions.keys()):
        if allowed_scenes is not None and scene_id not in allowed_scenes:
            continue

        payload = definitions[scene_id]
        if not isinstance(payload, MutableMapping):
            raise ValueError(
                f"Scene '{scene_id}' definition must be a mutable mapping to support replacements."
            )

        replacements: list[FieldReplacement] = []

        if allowed_fields is None or "scene_description" in allowed_fields:
            description = payload.get("description")
            if isinstance(description, str):
                result = _replace_field_text(
                    pattern,
                    replacement=replacement,
                    field_type="scene_description",
                    path="description",
                    text=description,
                )
                if result is not None:
                    payload["description"] = result.updated_text
                    replacements.append(result)

        if allowed_fields is None or "choice_description" in allowed_fields:
            raw_choices = payload.get("choices")
            if isinstance(raw_choices, list):
                for choice in raw_choices:
                    if not isinstance(choice, MutableMapping):
                        continue
                    command = choice.get("command")
                    description = choice.get("description")
                    if not isinstance(description, str):
                        continue
                    path = (
                        f"choices.{command}.description"
                        if isinstance(command, str)
                        else "choices[].description"
                    )
                    result = _replace_field_text(
                        pattern,
                        replacement=replacement,
                        field_type="choice_description",
                        path=path,
                        text=description,
                    )
                    if result is not None:
                        choice["description"] = result.updated_text
                        replacements.append(result)

        if allowed_fields is None or allowed_fields & {
            "transition_narration",
            "transition_failure_narration",
            "override_narration",
        }:
            raw_transitions = payload.get("transitions")
            if isinstance(raw_transitions, MutableMapping):
                for command, transition in raw_transitions.items():
                    if not isinstance(transition, MutableMapping):
                        continue

                    if (
                        allowed_fields is None
                        or "transition_narration" in allowed_fields
                    ):
                        narration = transition.get("narration")
                        if isinstance(narration, str):
                            path = (
                                f"transitions.{command}.narration"
                                if isinstance(command, str)
                                else "transitions[].narration"
                            )
                            result = _replace_field_text(
                                pattern,
                                replacement=replacement,
                                field_type="transition_narration",
                                path=path,
                                text=narration,
                            )
                            if result is not None:
                                transition["narration"] = result.updated_text
                                replacements.append(result)

                    if (
                        allowed_fields is None
                        or "transition_failure_narration" in allowed_fields
                    ):
                        failure = transition.get("failure_narration")
                        if isinstance(failure, str):
                            path = (
                                f"transitions.{command}.failure_narration"
                                if isinstance(command, str)
                                else "transitions[].failure_narration"
                            )
                            result = _replace_field_text(
                                pattern,
                                replacement=replacement,
                                field_type="transition_failure_narration",
                                path=path,
                                text=failure,
                            )
                            if result is not None:
                                transition["failure_narration"] = result.updated_text
                                replacements.append(result)

                    if allowed_fields is None or "override_narration" in allowed_fields:
                        overrides = transition.get("narration_overrides")
                        if isinstance(overrides, list):
                            for index, override in enumerate(overrides):
                                if not isinstance(override, MutableMapping):
                                    continue
                                narration = override.get("narration")
                                if not isinstance(narration, str):
                                    continue
                                path = (
                                    f"transitions.{command}.narration_overrides[{index}].narration"
                                    if isinstance(command, str)
                                    else "transitions[].narration_overrides[].narration"
                                )
                                result = _replace_field_text(
                                    pattern,
                                    replacement=replacement,
                                    field_type="override_narration",
                                    path=path,
                                    text=narration,
                                )
                                if result is not None:
                                    override["narration"] = result.updated_text
                                    replacements.append(result)

        if replacements:
            replacements.sort(key=lambda item: (item.field_type, item.path))
            scene_results.append(
                SceneReplacementResult(
                    scene_id=scene_id, replacements=tuple(replacements)
                )
            )

    return ReplacementResults(
        query=normalised_query,
        replacement_text=replacement,
        results=tuple(scene_results),
    )


def find_references(
    scenes: Mapping[str, _SceneLike],
    identifier: str,
    *,
    categories: Collection[ReferenceCategory] | None = None,
    reference_types: Collection[ReferenceType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> ReferenceResults:
    """Locate structured references to ``identifier`` within ``scenes``.

    The search inspects transition targets, inventory interactions, and history
    usage across both base transitions and conditional narration overrides. The
    ``identifier`` must be a non-empty string and comparisons are case-sensitive.

    Callers can restrict the results to specific ``categories`` (scene, item, or
    history references), particular ``reference_types`` (e.g. ``transition_target``
    or ``override_history_record``), or a subset of ``allowed_scene_ids``.
    """

    normalised_identifier = identifier.strip()
    if not normalised_identifier:
        raise ValueError("Reference identifier must not be empty.")

    allowed_categories: frozenset[ReferenceCategory] | None
    if categories is not None:
        allowed_categories = frozenset(categories)
    else:
        allowed_categories = None
    if (
        allowed_categories is not None
        and not allowed_categories <= _REFERENCE_CATEGORIES
    ):
        invalid = sorted(
            str(category) for category in allowed_categories - _REFERENCE_CATEGORIES
        )
        joined = ", ".join(invalid)
        raise ValueError(f"Unsupported reference categories: {joined}.")

    allowed_types: frozenset[ReferenceType] | None
    if reference_types is not None:
        allowed_types = frozenset(reference_types)
    else:
        allowed_types = None
    if allowed_types is not None and not allowed_types <= _REFERENCE_TYPES:
        invalid = sorted(
            str(reference_type) for reference_type in allowed_types - _REFERENCE_TYPES
        )
        joined = ", ".join(invalid)
        raise ValueError(f"Unsupported reference types: {joined}.")

    allowed_scenes: frozenset[str] | None
    if allowed_scene_ids is not None:
        allowed_scenes = frozenset(allowed_scene_ids)
    else:
        allowed_scenes = None

    results: list[SceneReferenceResult] = []

    def _should_include(reference_type: ReferenceType) -> bool:
        category = _REFERENCE_TYPE_TO_CATEGORY[reference_type]
        if allowed_categories is not None and category not in allowed_categories:
            return False
        if allowed_types is not None and reference_type not in allowed_types:
            return False
        return True

    for scene_id in sorted(scenes.keys()):
        if allowed_scenes is not None and scene_id not in allowed_scenes:
            continue

        scene = scenes[scene_id]
        matches: list[ReferenceMatch] = []

        def _maybe_add(
            reference_type: ReferenceType, path: str, value: str | None
        ) -> None:
            if value is None or value != normalised_identifier:
                return
            if not _should_include(reference_type):
                return
            category = _REFERENCE_TYPE_TO_CATEGORY[reference_type]
            matches.append(
                ReferenceMatch(
                    category=category,
                    reference_type=reference_type,
                    path=path,
                    value=value,
                )
            )

        for command in sorted(scene.transitions.keys()):
            transition = scene.transitions[command]

            _maybe_add(
                "transition_target",
                path=f"transitions.{command}.target",
                value=transition.target,
            )
            _maybe_add(
                "transition_item_award",
                path=f"transitions.{command}.item",
                value=transition.item,
            )

            for index, required in enumerate(transition.requires):
                _maybe_add(
                    "transition_item_requirement",
                    path=f"transitions.{command}.requires[{index}]",
                    value=required,
                )

            for index, consumed in enumerate(transition.consumes):
                _maybe_add(
                    "transition_item_consumption",
                    path=f"transitions.{command}.consumes[{index}]",
                    value=consumed,
                )

            for index, record in enumerate(transition.records):
                _maybe_add(
                    "transition_history_record",
                    path=f"transitions.{command}.records[{index}]",
                    value=record,
                )

            for override_index, override in enumerate(transition.narration_overrides):
                override_path = (
                    f"transitions.{command}.narration_overrides[{override_index}]"
                )

                for index, record in enumerate(override.records):
                    _maybe_add(
                        "override_history_record",
                        path=f"{override_path}.records[{index}]",
                        value=record,
                    )

                for index, entry in enumerate(override.requires_history_all):
                    _maybe_add(
                        "override_history_requirement_all",
                        path=f"{override_path}.requires_history_all[{index}]",
                        value=entry,
                    )

                for index, entry in enumerate(override.requires_history_any):
                    _maybe_add(
                        "override_history_requirement_any",
                        path=f"{override_path}.requires_history_any[{index}]",
                        value=entry,
                    )

                for index, entry in enumerate(override.forbids_history_any):
                    _maybe_add(
                        "override_history_forbidden",
                        path=f"{override_path}.forbids_history_any[{index}]",
                        value=entry,
                    )

                for index, entry in enumerate(override.requires_inventory_all):
                    _maybe_add(
                        "override_item_requirement_all",
                        path=f"{override_path}.requires_inventory_all[{index}]",
                        value=entry,
                    )

                for index, entry in enumerate(override.requires_inventory_any):
                    _maybe_add(
                        "override_item_requirement_any",
                        path=f"{override_path}.requires_inventory_any[{index}]",
                        value=entry,
                    )

                for index, entry in enumerate(override.forbids_inventory_any):
                    _maybe_add(
                        "override_item_forbidden",
                        path=f"{override_path}.forbids_inventory_any[{index}]",
                        value=entry,
                    )

        if matches:
            matches.sort(key=lambda match: (match.reference_type, match.path))
            results.append(
                SceneReferenceResult(scene_id=scene_id, matches=tuple(matches))
            )

    return ReferenceResults(
        identifier=normalised_identifier,
        results=tuple(results),
    )


def find_references_in_definitions(
    definitions: Mapping[str, Any],
    identifier: str,
    *,
    categories: Collection[ReferenceCategory] | None = None,
    reference_types: Collection[ReferenceType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> ReferenceResults:
    """Parse scene definitions and locate references to ``identifier``."""

    from .scripted_story_engine import load_scenes_from_mapping

    scenes = load_scenes_from_mapping(definitions)
    return find_references(
        cast(Mapping[str, _SceneLike], scenes),
        identifier,
        categories=categories,
        reference_types=reference_types,
        allowed_scene_ids=allowed_scene_ids,
    )


def find_references_in_file(
    path: str | Path,
    identifier: str,
    *,
    categories: Collection[ReferenceCategory] | None = None,
    reference_types: Collection[ReferenceType] | None = None,
    allowed_scene_ids: Collection[str] | None = None,
) -> ReferenceResults:
    """Load scene definitions from ``path`` and locate references."""

    from .scripted_story_engine import load_scenes_from_file

    scenes = load_scenes_from_file(path)
    return find_references(
        cast(Mapping[str, _SceneLike], scenes),
        identifier,
        categories=categories,
        reference_types=reference_types,
        allowed_scene_ids=allowed_scene_ids,
    )


def _iter_field_matches(
    pattern: re.Pattern[str],
    *,
    field_type: FieldType,
    path: str,
    text: str,
) -> Iterable[FieldMatch]:
    """Yield field matches for ``text`` using ``pattern``."""

    if not text:
        return []

    spans = [TextSpan(match.start(), match.end()) for match in pattern.finditer(text)]
    if not spans:
        return []

    return [FieldMatch(field_type=field_type, path=path, text=text, spans=tuple(spans))]


def _replace_field_text(
    pattern: re.Pattern[str],
    *,
    replacement: str,
    field_type: FieldType,
    path: str,
    text: str,
) -> FieldReplacement | None:
    """Return a replacement record for ``text`` or ``None`` when no match."""

    if not text:
        return None

    spans = [TextSpan(match.start(), match.end()) for match in pattern.finditer(text)]
    if not spans:
        return None

    updated_text = pattern.sub(replacement, text)
    return FieldReplacement(
        field_type=field_type,
        path=path,
        original_text=text,
        updated_text=updated_text,
        spans=tuple(spans),
    )


__all__ = [
    "FieldMatch",
    "FieldType",
    "SceneSearchResult",
    "SearchResults",
    "TextSpan",
    "search_scene_text",
    "search_scene_text_from_definitions",
    "search_scene_text_from_file",
    "FieldReplacement",
    "SceneReplacementResult",
    "ReplacementResults",
    "replace_scene_text_in_definitions",
    "ReferenceCategory",
    "ReferenceType",
    "ReferenceMatch",
    "SceneReferenceResult",
    "ReferenceResults",
    "find_references",
    "find_references_in_definitions",
    "find_references_in_file",
]
