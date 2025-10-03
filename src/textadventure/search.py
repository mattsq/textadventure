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


class _ChoiceLike(Protocol):
    command: str
    description: str


class _OverrideLike(Protocol):
    narration: str


class _TransitionLike(Protocol):
    narration: str
    failure_narration: str | None
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


__all__ = [
    "FieldMatch",
    "FieldType",
    "SceneSearchResult",
    "SearchResults",
    "TextSpan",
    "search_scene_text",
    "search_scene_text_from_definitions",
    "search_scene_text_from_file",
]
