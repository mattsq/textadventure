"""FastAPI application exposing read-only scene management endpoints."""

from __future__ import annotations

import difflib
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import resources
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Literal, Sequence, cast, get_args

from fastapi import FastAPI, HTTPException, Query
from functools import partial

from starlette.background import BackgroundTask
from starlette.responses import JSONResponse
from pydantic import BaseModel, Field, field_serializer

from ..analytics import (
    AdventureQualityReport,
    AdventureReachabilityReport,
    ItemFlowReport,
    ItemRequirement,
    ItemSource,
    ItemConsumption,
    _SceneLike as _AnalyticsSceneLike,
    assess_adventure_quality,
    analyse_item_flow,
    compute_scene_reachability,
)
from ..search import FieldType, SearchResults, _SceneLike, search_scene_text
from ..scripted_story_engine import load_scenes_from_mapping

ValidationStatus = Literal["valid", "warnings", "errors"]
DiffStatus = Literal["added", "removed", "modified"]


class ExportFormat(str, Enum):
    """Available formatting styles for exported scene JSON."""

    MINIFIED = "minified"
    PRETTY = "pretty"


class FormattedJSONResponse(JSONResponse):
    """JSON response that respects minified vs pretty-print formatting styles."""

    def __init__(
        self,
        content: Any,
        *,
        export_format: ExportFormat,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = "application/json",
        background: BackgroundTask | None = None,
    ) -> None:
        self._export_format = export_format
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
        )

    def render(self, content: Any) -> bytes:
        dumps = _dumps_for_export_format(self._export_format)
        return dumps(content).encode("utf-8")


class Pagination(BaseModel):
    """Pagination metadata returned alongside collection responses."""

    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total_items: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)


class SceneSummary(BaseModel):
    """Lightweight representation of a scene for overview lists."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus
    updated_at: datetime

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class SceneListResponse(BaseModel):
    """Response envelope for the scene collection endpoint."""

    data: list[SceneSummary]
    pagination: Pagination


class TextSpanResource(BaseModel):
    """Range describing where a search hit occurred within text."""

    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)


class FieldMatchResource(BaseModel):
    """Description of an individual field that matched a search query."""

    field_type: FieldType
    path: str
    text: str
    spans: list[TextSpanResource]
    match_count: int


class SceneSearchResultResource(BaseModel):
    """Aggregated search matches for a single scene."""

    scene_id: str
    match_count: int
    matches: list[FieldMatchResource]


class SceneSearchResponse(BaseModel):
    """Response payload describing search results across scenes."""

    query: str
    total_results: int
    total_matches: int
    results: list[SceneSearchResultResource]


class SceneCommandIssueResource(BaseModel):
    """Issue descriptor referencing a scene command."""

    scene_id: str
    command: str


class SceneOverrideIssueResource(BaseModel):
    """Issue descriptor referencing a conditional narration override."""

    scene_id: str
    command: str
    index: int = Field(..., ge=0)


class QualityIssuesResource(BaseModel):
    """Aggregated quality issues detected across the adventure."""

    issue_count: int
    scenes_missing_description: list[str] = Field(default_factory=list)
    choices_missing_description: list[SceneCommandIssueResource] = Field(
        default_factory=list
    )
    transitions_missing_narration: list[SceneCommandIssueResource] = Field(
        default_factory=list
    )
    gated_transitions_missing_failure: list[SceneCommandIssueResource] = Field(
        default_factory=list
    )
    conditional_overrides_missing_narration: list[SceneOverrideIssueResource] = Field(
        default_factory=list
    )


class SceneReachabilityResource(BaseModel):
    """Summary describing which scenes are reachable from the start."""

    start_scene: str
    reachable_scenes: list[str]
    unreachable_scenes: list[str]
    reachable_count: int
    unreachable_count: int
    total_scene_count: int
    fully_reachable: bool


class ItemReferenceResource(BaseModel):
    """Location where an item is referenced within a scene."""

    scene_id: str
    command: str


class ItemFlowDetailsResource(BaseModel):
    """Summary describing how a specific item flows through the adventure."""

    item: str
    sources: list[ItemReferenceResource] = Field(default_factory=list)
    requirements: list[ItemReferenceResource] = Field(default_factory=list)
    consumptions: list[ItemReferenceResource] = Field(default_factory=list)
    is_orphaned: bool
    is_missing_source: bool
    has_surplus_awards: bool
    has_consumption_deficit: bool


class ItemFlowSummaryResource(BaseModel):
    """Aggregate view of item flow issues across the adventure."""

    items: list[ItemFlowDetailsResource] = Field(default_factory=list)
    orphaned_items: list[str] = Field(default_factory=list)
    items_missing_sources: list[str] = Field(default_factory=list)
    items_with_surplus_awards: list[str] = Field(default_factory=list)
    items_with_consumption_deficit: list[str] = Field(default_factory=list)


class SceneValidationReport(BaseModel):
    """Combined validation output for the current adventure dataset."""

    generated_at: datetime
    quality: QualityIssuesResource
    reachability: SceneReachabilityResource
    item_flow: ItemFlowSummaryResource

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


class SceneValidationResponse(BaseModel):
    """Response envelope for the validation endpoint."""

    data: SceneValidationReport


class SceneExportMetadata(BaseModel):
    """Versioning and backup metadata for exported scene datasets."""

    version_id: str
    checksum: str
    suggested_filename: str


class SceneExportResponse(BaseModel):
    """Payload containing a full export of the current scene dataset."""

    generated_at: datetime
    scenes: dict[str, Any]
    metadata: SceneExportMetadata

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


class SceneImportRequest(BaseModel):
    """Request payload for validating uploaded scene definitions."""

    scenes: dict[str, Any] = Field(
        ...,
        description=(
            "Mapping of scene identifiers to their definitions mirroring the export format."
        ),
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version identifier for the uploaded dataset. "
            "Legacy versions are automatically migrated when supported."
        ),
    )
    start_scene: str | None = Field(
        None,
        description=(
            "Optional scene identifier to use as the reachability starting point. "
            "Defaults to the first scene in the payload when omitted."
        ),
    )


class ImportStrategy(str, Enum):
    """Supported strategies for applying uploaded scene datasets."""

    MERGE = "merge"
    REPLACE = "replace"


class SceneImportPlan(BaseModel):
    """Summary of the changes that would occur for a given import strategy."""

    strategy: ImportStrategy
    new_scene_ids: list[str] = Field(
        default_factory=list,
        description="Scenes that are only present in the uploaded dataset.",
    )
    updated_scene_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Scenes that exist in both datasets but whose definitions would change."
        ),
    )
    unchanged_scene_ids: list[str] = Field(
        default_factory=list,
        description="Scenes that exist in both datasets with identical definitions.",
    )
    removed_scene_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Scenes from the current dataset that would be removed when applying the"
            " strategy."
        ),
    )


class SceneImportResponse(BaseModel):
    """Response describing the outcome of validating an uploaded dataset."""

    scene_count: int = Field(..., ge=0)
    start_scene: str
    validation: SceneValidationReport
    plans: list[SceneImportPlan] = Field(
        default_factory=list,
        description=(
            "Summaries of how the uploaded dataset would affect the existing scenes"
            " when applying supported import strategies."
        ),
    )


class SceneDiffRequest(BaseModel):
    """Request payload for computing a diff against the current dataset."""

    scenes: dict[str, Any] = Field(
        ...,
        description=(
            "Mapping of scene identifiers to their definitions mirroring the export format."
        ),
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version identifier for the uploaded dataset. "
            "Legacy versions are automatically migrated when supported."
        ),
    )


class SceneDiffEntry(BaseModel):
    """Diff output for a single scene compared against the current dataset."""

    scene_id: str
    status: DiffStatus
    diff: str = Field(
        ...,
        description="Unified diff describing the changes for the scene in Git-style format.",
    )
    diff_html: str = Field(
        ...,
        description=(
            "HTML table representing the scene diff for visual rendering in UIs."
        ),
    )


class SceneDiffSummary(BaseModel):
    """High-level summary of scene-level differences."""

    added_scene_ids: list[str] = Field(default_factory=list)
    removed_scene_ids: list[str] = Field(default_factory=list)
    modified_scene_ids: list[str] = Field(default_factory=list)
    unchanged_scene_ids: list[str] = Field(default_factory=list)


class SceneDiffResponse(BaseModel):
    """Response payload containing scene diff output."""

    summary: SceneDiffSummary
    entries: list[SceneDiffEntry] = Field(default_factory=list)


@dataclass(frozen=True)
class SceneBackupResult:
    """Details about a backup snapshot created before importing scenes."""

    path: Path
    version_id: str
    checksum: str
    generated_at: datetime


class SceneVersionInfo(BaseModel):
    """Metadata describing a concrete scene dataset version."""

    generated_at: datetime
    version_id: str
    checksum: str

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


class SceneRollbackRequest(BaseModel):
    """Request payload describing the backup dataset to restore."""

    scenes: dict[str, Any] = Field(
        ...,
        description="Mapping of scene identifiers mirroring the export format.",
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version for the uploaded dataset. Legacy payloads are"
            " migrated automatically when supported."
        ),
    )
    generated_at: datetime | None = Field(
        None,
        description=(
            "Timestamp associated with the backup snapshot. When omitted, the"
            " current time is used in the rollback plan metadata."
        ),
    )


class SceneRollbackResponse(BaseModel):
    """Response payload summarising how to revert to a backup dataset."""

    current: SceneVersionInfo = Field(
        ..., description="Metadata about the currently bundled dataset."
    )
    target: SceneVersionInfo = Field(
        ..., description="Metadata about the backup dataset being restored."
    )
    summary: SceneDiffSummary
    entries: list[SceneDiffEntry] = Field(default_factory=list)
    plan: SceneImportPlan = Field(
        ..., description="Change summary for replacing the current dataset."
    )


class SceneBranchPlanRequest(BaseModel):
    """Request payload describing a proposed storyline branch dataset."""

    branch_name: str = Field(
        ..., min_length=1, description="Human readable name for the new branch."
    )
    scenes: dict[str, Any] = Field(
        ...,
        description="Mapping of scene identifiers mirroring the export format.",
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version for the uploaded dataset. Legacy payloads are"
            " migrated automatically when supported."
        ),
    )
    generated_at: datetime | None = Field(
        None,
        description=(
            "Timestamp associated with the branch dataset. When omitted, the"
            " current time is used in the plan metadata."
        ),
    )
    base_version_id: str | None = Field(
        None,
        description=(
            "Optional version identifier clients expect the branch to diverge"
            " from. Allows the service to flag if the bundled dataset has"
            " changed since the client exported it."
        ),
    )


class SceneBranchPlanResponse(BaseModel):
    """Response payload summarising how to spin off a new storyline branch."""

    branch_name: str = Field(
        ..., description="Normalised name that will identify the branch."
    )
    base: SceneVersionInfo = Field(
        ..., description="Metadata describing the current bundled dataset."
    )
    target: SceneVersionInfo = Field(
        ..., description="Metadata for the proposed branch dataset."
    )
    expected_base_version_id: str | None = Field(
        None,
        description=(
            "Version id supplied by the client when preparing the branch plan."
        ),
    )
    base_version_matches: bool = Field(
        ..., description="Whether the expected base matches the bundled dataset."
    )
    summary: SceneDiffSummary
    entries: list[SceneDiffEntry] = Field(default_factory=list)
    plans: list[SceneImportPlan] = Field(
        ..., description="Available import strategies for applying the branch."
    )


CURRENT_SCENE_SCHEMA_VERSION = 2


def _migrate_scene_dataset(
    scenes: Mapping[str, Any], *, schema_version: int | None
) -> dict[str, Any]:
    """Return a schema-compatible mapping for ``scenes``.

    Legacy datasets can specify ``schema_version`` so the service can migrate the
    structure before running validation. When ``schema_version`` is omitted or
    matches :data:`CURRENT_SCENE_SCHEMA_VERSION`, the payload is returned as-is
    (with shallow copies of the scene dictionaries). Unsupported versions raise
    :class:`ValueError` to surface actionable feedback to API clients.
    """

    normalised: dict[str, Any] = {
        scene_id: _ensure_scene_mapping(scene_id, payload)
        for scene_id, payload in scenes.items()
    }

    if schema_version is None or schema_version == CURRENT_SCENE_SCHEMA_VERSION:
        return normalised

    if schema_version > CURRENT_SCENE_SCHEMA_VERSION:
        raise ValueError("Uploaded schema version is newer than this server supports.")

    if schema_version < 1:
        raise ValueError("Schema version must be greater than or equal to 1.")

    if schema_version == 1:
        return {
            scene_id: _migrate_scene_v1(scene_id, payload)
            for scene_id, payload in normalised.items()
        }

    raise ValueError(
        f"Unsupported schema version '{schema_version}'. Upgrade the dataset or "
        "server before retrying."
    )


def _ensure_scene_mapping(scene_id: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"Scene '{scene_id}' must be a JSON object.")
    return dict(payload)


def _migrate_scene_v1(scene_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Convert schema version 1 scenes to the current structure."""

    migrated = dict(payload)

    transitions = migrated.get("transitions")
    if isinstance(transitions, list):
        converted: dict[str, Any] = {}
        for entry in transitions:
            if not isinstance(entry, Mapping):
                raise ValueError(
                    f"Transition entries for scene '{scene_id}' must be objects."
                )
            command = entry.get("command")
            if not isinstance(command, str) or not command:
                raise ValueError(
                    f"Legacy transition entries require a non-empty command for scene '{scene_id}'."
                )
            if command in converted:
                raise ValueError(
                    f"Duplicate transition command '{command}' in scene '{scene_id}'."
                )
            converted[command] = {
                key: value for key, value in entry.items() if key != "command"
            }
        migrated["transitions"] = converted
    elif isinstance(transitions, Mapping):
        migrated["transitions"] = dict(transitions)
    elif transitions is None:
        migrated["transitions"] = {}
    else:
        raise ValueError(
            f"Transitions for scene '{scene_id}' must be a list or object in legacy datasets."
        )

    choices = migrated.get("choices")
    if isinstance(choices, Mapping):
        converted_choices: list[dict[str, Any]] = []
        for command, choice_payload in choices.items():
            if not isinstance(command, str) or not command:
                raise ValueError(
                    f"Legacy choices require string commands for scene '{scene_id}'."
                )
            if any(choice.get("command") == command for choice in converted_choices):
                raise ValueError(
                    f"Duplicate choice command '{command}' in scene '{scene_id}'."
                )
            if isinstance(choice_payload, Mapping):
                choice_data = {"command": command, **dict(choice_payload)}
            else:
                choice_data = {"command": command, "description": str(choice_payload)}
            converted_choices.append(choice_data)
        migrated["choices"] = converted_choices
    elif isinstance(choices, list):
        migrated["choices"] = list(choices)
    elif choices is None:
        migrated["choices"] = []
    else:
        raise ValueError(
            f"Choices for scene '{scene_id}' must be a list or object in legacy datasets."
        )

    return migrated


def _parse_field_type_filters(value: str | None) -> list[FieldType] | None:
    """Parse comma-separated field types into validated values."""

    if value is None:
        return None

    raw_values = [candidate.strip() for candidate in value.split(",")]
    filtered = [candidate for candidate in raw_values if candidate]
    if not filtered:
        return []

    allowed = set(get_args(FieldType))
    invalid = [candidate for candidate in filtered if candidate not in allowed]
    if invalid:
        joined = ", ".join(sorted(invalid))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported field_types value(s): {joined}.",
        )

    return [cast(FieldType, candidate) for candidate in filtered]


def _parse_validation_filters(value: str | None) -> list[ValidationStatus] | None:
    """Parse comma-separated validation statuses into validated values."""

    if value is None:
        return None

    raw_values = [candidate.strip() for candidate in value.split(",")]
    filtered = [candidate for candidate in raw_values if candidate]
    if not filtered:
        return []

    allowed = set(get_args(ValidationStatus))
    invalid = [candidate for candidate in filtered if candidate not in allowed]
    if invalid:
        joined = ", ".join(sorted(invalid))
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported validation_statuses value(s): {joined}.",
        )

    return [cast(ValidationStatus, candidate) for candidate in filtered]


def _parse_scene_id_filter(value: str | None) -> list[str] | None:
    """Parse comma-separated scene identifiers for export filtering."""

    if value is None:
        return None

    parts = [candidate.strip() for candidate in value.split(",")]
    filtered = [candidate for candidate in parts if candidate]
    if not filtered:
        raise ValueError("At least one scene id must be provided.")

    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in filtered:
        if candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)

    return ordered


@dataclass(frozen=True)
class SceneSummaryData:
    """Internal representation of a scene summary prior to serialisation."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus
    updated_at: datetime


def _normalise_scene_payload(payload: Mapping[str, Any]) -> Any:
    """Return a canonical representation for comparing scene payloads."""

    try:
        # Serialise with sorted keys to ensure deterministic ordering before
        # parsing back into basic Python types for equality comparison.
        return json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    except (TypeError, ValueError):
        # Fall back to the raw payload when serialisation fails so comparisons
        # still have a best-effort chance of succeeding.
        return payload


def _serialise_scene_lines(payload: Any) -> list[str]:
    """Return indented JSON lines for ``payload`` suitable for unified diffs."""

    try:
        serialised = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        serialised = repr(payload)
    return serialised.splitlines()


def _format_scene_diff(
    scene_id: str,
    *,
    current: Any | None,
    incoming: Any | None,
) -> str:
    """Return a unified diff between ``current`` and ``incoming`` payloads."""

    current_lines = _serialise_scene_lines(current) if current is not None else []
    incoming_lines = _serialise_scene_lines(incoming) if incoming is not None else []

    diff_lines = difflib.unified_diff(
        current_lines,
        incoming_lines,
        fromfile=f"current/{scene_id}",
        tofile=f"incoming/{scene_id}",
        lineterm="",
    )
    return "\n".join(diff_lines)


def _format_scene_diff_html(
    scene_id: str,
    *,
    current: Any | None,
    incoming: Any | None,
) -> str:
    """Return an HTML table representing the diff between scene payloads."""

    current_lines = _serialise_scene_lines(current) if current is not None else []
    incoming_lines = _serialise_scene_lines(incoming) if incoming is not None else []

    html_diff = difflib.HtmlDiff(wrapcolumn=80)
    table = html_diff.make_table(
        current_lines,
        incoming_lines,
        fromdesc=f"current/{scene_id}",
        todesc=f"incoming/{scene_id}",
        context=True,
        numlines=3,
    )
    return table.strip()


def _compute_import_plans(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> list[SceneImportPlan]:
    """Compute change summaries for merge and replace import strategies."""

    existing_normalised = {
        scene_id: _normalise_scene_payload(payload)
        for scene_id, payload in existing.items()
    }
    incoming_normalised = {
        scene_id: _normalise_scene_payload(payload)
        for scene_id, payload in incoming.items()
    }

    existing_ids = set(existing_normalised)
    incoming_ids = set(incoming_normalised)
    shared_ids = sorted(existing_ids & incoming_ids)

    unchanged: list[str] = []
    updated: list[str] = []
    for scene_id in shared_ids:
        if existing_normalised[scene_id] == incoming_normalised[scene_id]:
            unchanged.append(scene_id)
        else:
            updated.append(scene_id)

    new_ids = sorted(incoming_ids - existing_ids)
    removed_ids = sorted(existing_ids - incoming_ids)

    merge_plan = SceneImportPlan(
        strategy=ImportStrategy.MERGE,
        new_scene_ids=new_ids,
        updated_scene_ids=updated,
        unchanged_scene_ids=unchanged,
        removed_scene_ids=[],
    )
    replace_plan = SceneImportPlan(
        strategy=ImportStrategy.REPLACE,
        new_scene_ids=new_ids,
        updated_scene_ids=updated,
        unchanged_scene_ids=unchanged,
        removed_scene_ids=removed_ids,
    )

    return [merge_plan, replace_plan]


def _compute_scene_diffs(
    existing: Mapping[str, Any], incoming: Mapping[str, Any]
) -> tuple[SceneDiffSummary, list[SceneDiffEntry]]:
    """Return diff summary and entries comparing ``existing`` to ``incoming``."""

    existing_normalised = {
        scene_id: _normalise_scene_payload(_ensure_scene_mapping(scene_id, payload))
        for scene_id, payload in existing.items()
    }
    incoming_normalised = {
        scene_id: _normalise_scene_payload(payload)
        for scene_id, payload in incoming.items()
    }

    existing_ids = set(existing_normalised)
    incoming_ids = set(incoming_normalised)
    shared_ids = sorted(existing_ids & incoming_ids)

    unchanged_ids: list[str] = []
    modified_ids: list[str] = []
    for scene_id in shared_ids:
        if existing_normalised[scene_id] == incoming_normalised[scene_id]:
            unchanged_ids.append(scene_id)
        else:
            modified_ids.append(scene_id)

    added_ids = sorted(incoming_ids - existing_ids)
    removed_ids = sorted(existing_ids - incoming_ids)

    summary = SceneDiffSummary(
        added_scene_ids=added_ids,
        removed_scene_ids=removed_ids,
        modified_scene_ids=modified_ids,
        unchanged_scene_ids=unchanged_ids,
    )

    entries: list[SceneDiffEntry] = []

    for scene_id in added_ids:
        entries.append(
            SceneDiffEntry(
                scene_id=scene_id,
                status="added",
                diff=_format_scene_diff(
                    scene_id, current=None, incoming=incoming_normalised[scene_id]
                ),
                diff_html=_format_scene_diff_html(
                    scene_id, current=None, incoming=incoming_normalised[scene_id]
                ),
            )
        )

    for scene_id in removed_ids:
        entries.append(
            SceneDiffEntry(
                scene_id=scene_id,
                status="removed",
                diff=_format_scene_diff(
                    scene_id, current=existing_normalised[scene_id], incoming=None
                ),
                diff_html=_format_scene_diff_html(
                    scene_id, current=existing_normalised[scene_id], incoming=None
                ),
            )
        )

    for scene_id in modified_ids:
        entries.append(
            SceneDiffEntry(
                scene_id=scene_id,
                status="modified",
                diff=_format_scene_diff(
                    scene_id,
                    current=existing_normalised[scene_id],
                    incoming=incoming_normalised[scene_id],
                ),
                diff_html=_format_scene_diff_html(
                    scene_id,
                    current=existing_normalised[scene_id],
                    incoming=incoming_normalised[scene_id],
                ),
            )
        )

    return summary, entries


class SceneRepository:
    """Loader responsible for retrieving the bundled scripted scene data."""

    def __init__(
        self,
        *,
        package: str = "textadventure.data",
        resource_name: str = "scripted_scenes.json",
    ) -> None:
        self._package = package
        self._resource_name = resource_name

    def load(self) -> tuple[Mapping[str, Any], datetime]:
        """Load scene definitions along with their last modified timestamp."""

        data_resource = resources.files(self._package).joinpath(self._resource_name)

        try:
            with resources.as_file(data_resource) as path:
                payload = _load_json(path)
                updated_at = _timestamp_for(path)
        except FileNotFoundError as exc:
            raise RuntimeError("Bundled scene data is missing.") from exc
        except OSError as exc:
            raise RuntimeError("Failed to read bundled scene data.") from exc

        if not isinstance(payload, Mapping):
            raise ValueError(
                "Scene data must be a mapping of identifiers to definitions."
            )

        return payload, updated_at


class SceneService:
    """Business logic supporting the API endpoints."""

    def __init__(self, repository: SceneRepository | None = None) -> None:
        self._repository = repository or SceneRepository()

    def list_scene_summaries(
        self,
        *,
        search: str | None,
        updated_after: datetime | None,
        include_validation: bool,
        page: int,
        page_size: int,
    ) -> SceneListResponse:
        definitions, dataset_timestamp = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)

        validation_map = (
            _compute_validation_statuses(cast(Mapping[str, Any], scenes))
            if include_validation
            else {}
        )

        summaries = [
            SceneSummaryData(
                id=scene_id,
                description=scene.description,
                choice_count=len(scene.choices),
                transition_count=len(scene.transitions),
                has_terminal_transition=_has_terminal_transition(
                    scene.transitions.values()
                ),
                validation_status=validation_map.get(scene_id, "valid"),
                updated_at=dataset_timestamp,
            )
            for scene_id, scene in scenes.items()
        ]

        if search:
            lowered_query = search.casefold()
            summaries = [
                summary
                for summary in summaries
                if lowered_query in summary.id.casefold()
                or lowered_query in summary.description.casefold()
            ]

        if updated_after is not None:
            threshold = _ensure_timezone(updated_after)
            summaries = [
                summary for summary in summaries if summary.updated_at > threshold
            ]

        total_items = len(summaries)
        total_pages = _compute_total_pages(total_items, page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        visible = summaries[start_index:end_index]

        response = SceneListResponse(
            data=[SceneSummary(**asdict(summary)) for summary in visible],
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )
        return response

    def get_scene_detail(
        self,
        scene_id: str,
        *,
        include_validation: bool,
    ) -> "SceneDetailResponse":
        """Return the full scene definition for ``scene_id``."""

        definitions, dataset_timestamp = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)

        try:
            scene = scenes[scene_id]
        except KeyError as exc:
            raise KeyError(f"Scene '{scene_id}' is not defined.") from exc

        resource = _build_scene_resource(scene_id, scene, dataset_timestamp)

        validation: SceneValidation | None = None
        if include_validation:
            validation = SceneValidation(
                issues=_collect_validation_issues(scene_id, scenes)
            )

        return SceneDetailResponse(data=resource, validation=validation)

    def search_scene_text(
        self,
        query: str,
        *,
        field_types: Sequence[FieldType] | FieldType | None = None,
        validation_statuses: (
            Sequence[ValidationStatus] | ValidationStatus | None
        ) = None,
    ) -> SearchResults:
        """Search scene text content for the provided ``query``."""

        definitions, _ = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)
        if field_types is None:
            field_type_filter: list[FieldType] | None = None
        elif isinstance(field_types, str):
            field_type_filter = [field_types]
        else:
            field_type_filter = list(field_types)

        if validation_statuses is None:
            status_filter: list[ValidationStatus] | None = None
        elif isinstance(validation_statuses, str):
            status_filter = [validation_statuses]
        else:
            status_filter = list(validation_statuses)
        allowed_scene_ids: set[str] | None = None

        if status_filter is not None:
            validation_map = _compute_validation_statuses(
                cast(Mapping[str, Any], scenes)
            )
            allowed_statuses = set(status_filter)
            allowed_scene_ids = {
                scene_id
                for scene_id, status in validation_map.items()
                if status in allowed_statuses
            }

        return search_scene_text(
            cast(Mapping[str, _SceneLike], scenes),
            query,
            field_types=field_type_filter,
            allowed_scene_ids=allowed_scene_ids,
        )

    def validate_scenes(
        self,
        *,
        start_scene: str = "starting-area",
    ) -> SceneValidationReport:
        """Run comprehensive validation checks across all scenes."""

        definitions, dataset_timestamp = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)
        scene_mapping = cast(Mapping[str, _AnalyticsSceneLike], scenes)

        return self._build_validation_report(
            scene_mapping,
            generated_at=dataset_timestamp,
            start_scene=start_scene,
        )

    def export_scenes(self, *, ids: Sequence[str] | None = None) -> SceneExportResponse:
        """Return the scene dataset for download, optionally filtered by id."""

        definitions, dataset_timestamp = self._repository.load()

        export_definitions: Mapping[str, Any] = definitions

        if ids is not None:
            if not ids:
                raise ValueError("At least one scene id must be provided.")

            missing = [scene_id for scene_id in ids if scene_id not in definitions]
            if missing:
                formatted = ", ".join(sorted(set(missing)))
                raise KeyError(f"Scene ids not defined: {formatted}.")

            export_definitions = {scene_id: definitions[scene_id] for scene_id in ids}

        try:
            serialisable: dict[str, Any] = json.loads(json.dumps(export_definitions))
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene data could not be serialised to JSON.") from exc

        checksum = _compute_scene_checksum(serialisable)
        version_id = _format_version_id(dataset_timestamp, checksum)

        return SceneExportResponse(
            generated_at=dataset_timestamp,
            scenes=serialisable,
            metadata=SceneExportMetadata(
                version_id=version_id,
                checksum=checksum,
                suggested_filename=_build_backup_filename(version_id),
            ),
        )

    def validate_import_payload(
        self,
        *,
        scenes: Mapping[str, Any],
        schema_version: int | None = None,
        start_scene: str | None = None,
    ) -> SceneImportResponse:
        """Validate uploaded scene definitions without persisting them."""

        if not scenes:
            raise ValueError("At least one scene must be provided for import.")

        existing_definitions, _ = self._repository.load()

        try:
            migrated_scenes = _migrate_scene_dataset(
                scenes, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        try:
            parsed_scenes = load_scenes_from_mapping(migrated_scenes)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        available_scene_ids = list(parsed_scenes)
        if not available_scene_ids:
            raise ValueError("At least one scene must be provided for import.")

        if start_scene is None:
            selected_start_scene = available_scene_ids[0]
        else:
            if start_scene not in parsed_scenes:
                raise ValueError(
                    f"Start scene '{start_scene}' is not defined in the uploaded data."
                )
            selected_start_scene = start_scene

        scene_mapping = cast(Mapping[str, _AnalyticsSceneLike], parsed_scenes)
        generated_at = datetime.now(timezone.utc)
        report = self._build_validation_report(
            scene_mapping,
            generated_at=generated_at,
            start_scene=selected_start_scene,
        )

        plans = _compute_import_plans(existing_definitions, migrated_scenes)

        return SceneImportResponse(
            scene_count=len(parsed_scenes),
            start_scene=selected_start_scene,
            validation=report,
            plans=plans,
        )

    def diff_scenes(
        self,
        *,
        scenes: Mapping[str, Any],
        schema_version: int | None = None,
    ) -> SceneDiffResponse:
        """Compute Git-style diffs between the current dataset and ``scenes``."""

        if not scenes:
            raise ValueError("At least one scene must be provided for diffing.")

        existing_definitions, _ = self._repository.load()

        try:
            migrated_scenes = _migrate_scene_dataset(
                scenes, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        summary, entries = _compute_scene_diffs(existing_definitions, migrated_scenes)

        return SceneDiffResponse(summary=summary, entries=entries)

    def plan_rollback(
        self,
        *,
        scenes: Mapping[str, Any],
        schema_version: int | None = None,
        generated_at: datetime | None = None,
    ) -> SceneRollbackResponse:
        """Plan how to restore a backup dataset without mutating state."""

        if not scenes:
            raise ValueError(
                "At least one scene must be provided for rollback planning."
            )

        existing_definitions, current_timestamp = self._repository.load()

        try:
            migrated_scenes = _migrate_scene_dataset(
                scenes, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        summary, entries = _compute_scene_diffs(existing_definitions, migrated_scenes)

        plans = _compute_import_plans(existing_definitions, migrated_scenes)
        replace_plan = next(
            (plan for plan in plans if plan.strategy is ImportStrategy.REPLACE), None
        )
        if replace_plan is None:
            replace_plan = SceneImportPlan(strategy=ImportStrategy.REPLACE)

        try:
            serialisable_current = json.loads(
                json.dumps(existing_definitions, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Current scene data could not be serialised to JSON."
            ) from exc

        try:
            serialisable_target = json.loads(
                json.dumps(migrated_scenes, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene data could not be serialised to JSON.") from exc

        current_checksum = _compute_scene_checksum(serialisable_current)
        current_generated_at = _ensure_timezone(current_timestamp)
        current_version_id = _format_version_id(current_generated_at, current_checksum)

        target_generated_at = (
            _ensure_timezone(generated_at)
            if generated_at is not None
            else datetime.now(timezone.utc)
        )
        target_checksum = _compute_scene_checksum(serialisable_target)
        target_version_id = _format_version_id(target_generated_at, target_checksum)

        return SceneRollbackResponse(
            current=SceneVersionInfo(
                generated_at=current_generated_at,
                version_id=current_version_id,
                checksum=current_checksum,
            ),
            target=SceneVersionInfo(
                generated_at=target_generated_at,
                version_id=target_version_id,
                checksum=target_checksum,
            ),
            summary=summary,
            entries=entries,
            plan=replace_plan,
        )

    def plan_branch(
        self,
        *,
        branch_name: str,
        scenes: Mapping[str, Any],
        schema_version: int | None = None,
        generated_at: datetime | None = None,
        expected_base_version: str | None = None,
    ) -> SceneBranchPlanResponse:
        """Plan how a new storyline branch diverges from the bundled dataset."""

        if not branch_name.strip():
            raise ValueError("Branch name must not be empty.")
        if not scenes:
            raise ValueError("At least one scene must be provided for branch planning.")

        normalised_name = branch_name.strip()

        existing_definitions, current_timestamp = self._repository.load()

        try:
            migrated_scenes = _migrate_scene_dataset(
                scenes, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        summary, entries = _compute_scene_diffs(existing_definitions, migrated_scenes)
        plans = _compute_import_plans(existing_definitions, migrated_scenes)

        try:
            serialisable_current = json.loads(
                json.dumps(existing_definitions, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "Current scene data could not be serialised to JSON."
            ) from exc

        try:
            serialisable_target = json.loads(
                json.dumps(migrated_scenes, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene data could not be serialised to JSON.") from exc

        current_generated_at = _ensure_timezone(current_timestamp)
        current_checksum = _compute_scene_checksum(serialisable_current)
        current_version_id = _format_version_id(current_generated_at, current_checksum)

        branch_generated_at = (
            _ensure_timezone(generated_at)
            if generated_at is not None
            else datetime.now(timezone.utc)
        )
        target_checksum = _compute_scene_checksum(serialisable_target)
        target_version_id = _format_version_id(branch_generated_at, target_checksum)

        base_matches = (
            True
            if expected_base_version is None
            else expected_base_version == current_version_id
        )

        return SceneBranchPlanResponse(
            branch_name=normalised_name,
            base=SceneVersionInfo(
                generated_at=current_generated_at,
                version_id=current_version_id,
                checksum=current_checksum,
            ),
            target=SceneVersionInfo(
                generated_at=branch_generated_at,
                version_id=target_version_id,
                checksum=target_checksum,
            ),
            expected_base_version_id=expected_base_version,
            base_version_matches=base_matches,
            summary=summary,
            entries=entries,
            plans=plans,
        )

    def create_backup(
        self,
        *,
        destination_dir: Path,
        export_format: ExportFormat = ExportFormat.PRETTY,
    ) -> SceneBackupResult:
        """Write the current scene dataset to ``destination_dir``."""

        export = self.export_scenes()
        destination_dir.mkdir(parents=True, exist_ok=True)

        filename = export.metadata.suggested_filename
        backup_path = destination_dir / filename

        dumps = _dumps_for_export_format(export_format)
        serialisable = json.loads(json.dumps(export.scenes, ensure_ascii=False))

        with backup_path.open("w", encoding="utf-8") as handle:
            handle.write(dumps(serialisable))

        return SceneBackupResult(
            path=backup_path,
            version_id=export.metadata.version_id,
            checksum=export.metadata.checksum,
            generated_at=export.generated_at,
        )

    def _build_validation_report(
        self,
        scene_mapping: Mapping[str, _AnalyticsSceneLike],
        *,
        generated_at: datetime,
        start_scene: str,
    ) -> SceneValidationReport:
        quality_report = assess_adventure_quality(scene_mapping)
        reachability_report = compute_scene_reachability(
            scene_mapping, start_scene=start_scene
        )
        item_flow_report = analyse_item_flow(scene_mapping)

        return SceneValidationReport(
            generated_at=generated_at,
            quality=_build_quality_resource(quality_report),
            reachability=_build_reachability_resource(reachability_report),
            item_flow=_build_item_flow_resource(item_flow_report),
        )


def create_app(scene_service: SceneService | None = None) -> FastAPI:
    """Create a FastAPI app exposing the scene management endpoints."""

    service = scene_service or SceneService()
    app = FastAPI(title="Text Adventure Scene API", version="0.1.0")

    @app.get("/api/scenes", response_model=SceneListResponse)
    def get_scenes(
        *,
        search: str | None = Query(
            None, description="Filter by id or description substring."
        ),
        updated_after: datetime | None = Query(
            None, description="Return scenes updated after the provided ISO timestamp."
        ),
        include_validation: bool = Query(
            True,
            description="Include aggregated validation status metadata.",
        ),
        page: int = Query(1, ge=1),
        page_size: int = Query(
            50,
            ge=1,
            le=200,
            description="Number of results to return per page (max 200).",
        ),
    ) -> SceneListResponse:
        try:
            return service.list_scene_summaries(
                search=search,
                updated_after=updated_after,
                include_validation=include_validation,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/scenes/{scene_id}", response_model=SceneDetailResponse)
    def get_scene(
        scene_id: str,
        *,
        include_validation: bool = Query(
            False,
            description="Include inline validation issues for the requested scene.",
        ),
    ) -> SceneDetailResponse:
        try:
            return service.get_scene_detail(
                scene_id=scene_id, include_validation=include_validation
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/api/search", response_model=SceneSearchResponse)
    def search_scenes(
        query: str = Query(
            ..., min_length=1, description="Case-insensitive text to search for."
        ),
        field_types: str | None = Query(
            None,
            description="Restrict matches to specific narrative fields (comma-separated).",
        ),
        validation_statuses: str | None = Query(
            None,
            description=(
                "Limit results to scenes matching the provided validation states "
                "(comma-separated)."
            ),
        ),
        limit: int = Query(
            50,
            ge=1,
            le=200,
            description="Maximum number of scenes to return (max 200).",
        ),
    ) -> SceneSearchResponse:
        try:
            results = service.search_scene_text(
                query=query,
                field_types=_parse_field_type_filters(field_types),
                validation_statuses=_parse_validation_filters(validation_statuses),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_search_response(results, limit=limit)

    @app.get("/api/scenes/validate", response_model=SceneValidationResponse)
    def validate_scenes(
        start_scene: str = Query(
            "starting-area",
            description="Scene identifier to use as the starting point for reachability analysis.",
        ),
    ) -> SceneValidationResponse:
        try:
            report = service.validate_scenes(start_scene=start_scene)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return SceneValidationResponse(data=report)

    @app.get("/api/export/scenes", response_model=None)
    def export_scenes(
        ids: str | None = Query(
            None,
            description=(
                "Comma-separated list of scene identifiers to export. "
                "When omitted, the full dataset is returned."
            ),
        ),
        format: ExportFormat = Query(
            ExportFormat.MINIFIED,
            description=(
                "Serialisation style for the JSON payload. "
                "Use 'pretty' for indented output or 'minified' for compact output."
            ),
        ),
    ) -> FormattedJSONResponse:
        try:
            parsed_ids = _parse_scene_id_filter(ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            export_format = (
                format if isinstance(format, ExportFormat) else ExportFormat(format)
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            export = service.export_scenes(ids=parsed_ids)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return FormattedJSONResponse(
            content=export.model_dump(),
            export_format=export_format,
        )

    @app.post("/api/import/scenes", response_model=SceneImportResponse)
    def import_scenes(payload: SceneImportRequest) -> SceneImportResponse:
        try:
            return service.validate_import_payload(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                start_scene=payload.start_scene,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/scenes/rollback", response_model=SceneRollbackResponse)
    def plan_rollback(payload: SceneRollbackRequest) -> SceneRollbackResponse:
        try:
            return service.plan_rollback(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                generated_at=payload.generated_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/scenes/branches/plan",
        response_model=SceneBranchPlanResponse,
    )
    def plan_branch(payload: SceneBranchPlanRequest) -> SceneBranchPlanResponse:
        try:
            return service.plan_branch(
                branch_name=payload.branch_name,
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                generated_at=payload.generated_at,
                expected_base_version=payload.base_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/api/scenes/diff", response_model=SceneDiffResponse)
    def diff_scenes(payload: SceneDiffRequest) -> SceneDiffResponse:
        try:
            return service.diff_scenes(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _dumps_for_export_format(export_format: ExportFormat) -> Callable[[Any], str]:
    if export_format is ExportFormat.PRETTY:
        return partial(json.dumps, indent=2, ensure_ascii=False)

    return partial(json.dumps, separators=(",", ":"), ensure_ascii=False)


def _timestamp_for(path: Path) -> datetime:
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(mtime, tz=timezone.utc)


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _compute_total_pages(total_items: int, page_size: int) -> int:
    if total_items == 0:
        return 0
    return (total_items + page_size - 1) // page_size


def _has_terminal_transition(transitions: Iterable[Any]) -> bool:
    for transition in transitions:
        if getattr(transition, "target", None) is None:
            return True
    return False


def _compute_validation_statuses(
    scenes: Mapping[str, Any],
) -> dict[str, ValidationStatus]:
    report = assess_adventure_quality(cast(Mapping[str, Any], scenes))

    error_scenes: set[str] = set(report.scenes_missing_description)
    error_scenes.update(scene for scene, _ in report.transitions_missing_narration)
    error_scenes.update(
        scene for scene, _, _ in report.conditional_overrides_missing_narration
    )

    warning_scenes: set[str] = set(
        scene for scene, _ in report.choices_missing_description
    )
    warning_scenes.update(
        scene for scene, _ in report.gated_transitions_missing_failure
    )

    validation_map: dict[str, ValidationStatus] = {}
    for scene_id in scenes:
        if scene_id in error_scenes:
            validation_map[scene_id] = "errors"
        elif scene_id in warning_scenes:
            validation_map[scene_id] = "warnings"
        else:
            validation_map[scene_id] = "valid"

    return validation_map


def _build_search_response(
    results: SearchResults,
    *,
    limit: int,
) -> SceneSearchResponse:
    limited_results = list(results.results[:limit])

    scene_resources: list[SceneSearchResultResource] = []
    for scene_result in limited_results:
        field_resources: list[FieldMatchResource] = []
        for field_match in scene_result.matches:
            span_resources = [
                TextSpanResource(start=span.start, end=span.end)
                for span in field_match.spans
            ]
            field_resources.append(
                FieldMatchResource(
                    field_type=field_match.field_type,
                    path=field_match.path,
                    text=field_match.text,
                    spans=span_resources,
                    match_count=field_match.match_count,
                )
            )

        scene_resources.append(
            SceneSearchResultResource(
                scene_id=scene_result.scene_id,
                match_count=scene_result.match_count,
                matches=field_resources,
            )
        )

    return SceneSearchResponse(
        query=results.query,
        total_results=results.total_results,
        total_matches=results.total_match_count,
        results=scene_resources,
    )


def _build_quality_resource(report: AdventureQualityReport) -> QualityIssuesResource:
    choices = [
        SceneCommandIssueResource(scene_id=scene, command=command)
        for scene, command in report.choices_missing_description
    ]
    transitions = [
        SceneCommandIssueResource(scene_id=scene, command=command)
        for scene, command in report.transitions_missing_narration
    ]
    gated = [
        SceneCommandIssueResource(scene_id=scene, command=command)
        for scene, command in report.gated_transitions_missing_failure
    ]
    overrides = [
        SceneOverrideIssueResource(scene_id=scene, command=command, index=index)
        for scene, command, index in report.conditional_overrides_missing_narration
    ]

    return QualityIssuesResource(
        issue_count=report.issue_count,
        scenes_missing_description=list(report.scenes_missing_description),
        choices_missing_description=choices,
        transitions_missing_narration=transitions,
        gated_transitions_missing_failure=gated,
        conditional_overrides_missing_narration=overrides,
    )


def _build_reachability_resource(
    report: AdventureReachabilityReport,
) -> SceneReachabilityResource:
    return SceneReachabilityResource(
        start_scene=report.start_scene,
        reachable_scenes=list(report.reachable_scenes),
        unreachable_scenes=list(report.unreachable_scenes),
        reachable_count=report.reachable_count,
        unreachable_count=report.unreachable_count,
        total_scene_count=report.total_scene_count,
        fully_reachable=report.fully_reachable,
    )


def _build_item_flow_resource(report: ItemFlowReport) -> ItemFlowSummaryResource:
    def _convert_references(
        entries: Iterable[ItemSource | ItemRequirement | ItemConsumption],
    ) -> list[ItemReferenceResource]:
        return [
            ItemReferenceResource(scene_id=entry.scene, command=entry.command)
            for entry in entries
        ]

    items: list[ItemFlowDetailsResource] = []
    for detail in report.items:
        items.append(
            ItemFlowDetailsResource(
                item=detail.item,
                sources=_convert_references(detail.sources),
                requirements=_convert_references(detail.requirements),
                consumptions=_convert_references(detail.consumptions),
                is_orphaned=detail.is_orphaned,
                is_missing_source=detail.is_missing_source,
                has_surplus_awards=detail.has_surplus_awards,
                has_consumption_deficit=detail.has_consumption_deficit,
            )
        )

    return ItemFlowSummaryResource(
        items=items,
        orphaned_items=list(report.orphaned_items),
        items_missing_sources=list(report.items_missing_sources),
        items_with_surplus_awards=list(report.items_with_surplus_awards),
        items_with_consumption_deficit=list(report.items_with_consumption_deficit),
    )


class ChoiceResource(BaseModel):
    """Representation of a single scene choice."""

    command: str
    description: str


class NarrationOverrideResource(BaseModel):
    """Conditional narration override description."""

    narration: str
    requires_history_all: list[str] = Field(default_factory=list)
    requires_history_any: list[str] = Field(default_factory=list)
    forbids_history_any: list[str] = Field(default_factory=list)
    requires_inventory_all: list[str] = Field(default_factory=list)
    requires_inventory_any: list[str] = Field(default_factory=list)
    forbids_inventory_any: list[str] = Field(default_factory=list)
    records: list[str] = Field(default_factory=list)


class TransitionResource(BaseModel):
    """Serialized representation of a transition."""

    narration: str
    target: str | None = None
    item: str | None = None
    requires: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    records: list[str] = Field(default_factory=list)
    failure_narration: str | None = None
    narration_overrides: list[NarrationOverrideResource] = Field(default_factory=list)


class SceneResource(BaseModel):
    """Full scene definition returned by the API."""

    id: str
    description: str
    choices: list[ChoiceResource]
    transitions: dict[str, TransitionResource]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialize_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class ValidationIssue(BaseModel):
    """Description of a validation issue detected for a scene."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str


class SceneValidation(BaseModel):
    """Collection of validation issues for a scene."""

    issues: list[ValidationIssue]


class SceneDetailResponse(BaseModel):
    """Response envelope for a single scene detail request."""

    data: SceneResource
    validation: SceneValidation | None = None


def _build_scene_resource(
    scene_id: str,
    scene: Any,
    dataset_timestamp: datetime,
) -> SceneResource:
    choices = [
        ChoiceResource(command=choice.command, description=choice.description)
        for choice in scene.choices
    ]

    transitions: dict[str, TransitionResource] = {}
    for command, transition in scene.transitions.items():
        overrides = [
            NarrationOverrideResource(
                narration=override.narration,
                requires_history_all=list(override.requires_history_all),
                requires_history_any=list(override.requires_history_any),
                forbids_history_any=list(override.forbids_history_any),
                requires_inventory_all=list(override.requires_inventory_all),
                requires_inventory_any=list(override.requires_inventory_any),
                forbids_inventory_any=list(override.forbids_inventory_any),
                records=list(override.records),
            )
            for override in transition.narration_overrides
        ]

        transitions[command] = TransitionResource(
            narration=transition.narration,
            target=transition.target,
            item=transition.item,
            requires=list(transition.requires),
            consumes=list(transition.consumes),
            records=list(transition.records),
            failure_narration=transition.failure_narration,
            narration_overrides=overrides,
        )

    return SceneResource(
        id=scene_id,
        description=scene.description,
        choices=choices,
        transitions=transitions,
        created_at=dataset_timestamp,
        updated_at=dataset_timestamp,
    )


def _compute_scene_checksum(scenes: Mapping[str, Any]) -> str:
    """Return a deterministic checksum for the provided scene mapping."""

    canonical = json.dumps(
        scenes,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _format_version_id(timestamp: datetime, checksum: str) -> str:
    """Derive a compact version identifier from the timestamp and checksum."""

    timestamp_utc = _ensure_timezone(timestamp).astimezone(timezone.utc)
    canonical = timestamp_utc.strftime("%Y%m%dT%H%M%SZ")
    return f"{canonical}-{checksum[:8]}"


def _build_backup_filename(version_id: str) -> str:
    """Return the suggested filename for backing up the export payload."""

    return f"scene-backup-{version_id}.json"


def _collect_validation_issues(
    scene_id: str,
    scenes: Mapping[str, Any],
) -> list[ValidationIssue]:
    report = assess_adventure_quality(cast(Mapping[str, Any], scenes))

    issues: list[ValidationIssue] = []

    if scene_id in report.scenes_missing_description:
        issues.append(
            ValidationIssue(
                severity="error",
                code="missing_scene_description",
                message="Scene description is empty.",
                path="description",
            )
        )

    for candidate_scene, command in report.choices_missing_description:
        if candidate_scene == scene_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_choice_description",
                    message=f"Choice '{command}' is missing a description.",
                    path=f"choices.{command}.description",
                )
            )

    for candidate_scene, command in report.transitions_missing_narration:
        if candidate_scene == scene_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_transition_narration",
                    message=f"Transition '{command}' is missing narration.",
                    path=f"transitions.{command}.narration",
                )
            )

    for candidate_scene, command in report.gated_transitions_missing_failure:
        if candidate_scene == scene_id:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="missing_failure_narration",
                    message=(
                        f"Transition '{command}' requires inventory but lacks failure narration."
                    ),
                    path=f"transitions.{command}.failure_narration",
                )
            )

    for (
        candidate_scene,
        command,
        index,
    ) in report.conditional_overrides_missing_narration:
        if candidate_scene == scene_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="missing_override_narration",
                    message=(
                        f"Narration override #{index + 1} for transition '{command}' is empty."
                    ),
                    path=f"transitions.{command}.narration_overrides[{index}].narration",
                )
            )

    issues.sort(key=lambda issue: (issue.path, issue.code))
    return issues
