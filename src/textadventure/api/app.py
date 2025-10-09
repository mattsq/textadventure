"""FastAPI application exposing scene management endpoints."""

from __future__ import annotations

import base64
import binascii
import difflib
import hashlib
import io
import json
import mimetypes
import os
import re
import shutil
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from importlib import resources
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Mapping,
    Literal,
    Sequence,
    cast,
    get_args,
)

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from functools import partial

from starlette.background import BackgroundTask
from starlette.responses import JSONResponse
from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)

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
from ..scripted_story_engine import ScriptedStoryEngine, load_scenes_from_mapping
from ..story_engine import StoryEngine, StoryEvent
from ..world_state import WorldState
from ..multi_agent import (
    MultiAgentCoordinator,
    ScriptedStoryAgent,
    QueuedAgentMessage,
)
from ..memory import MemoryRequest
from .backup import BackupUploadMetadata, BackupUploader, S3BackupUploader
from .settings import SceneApiSettings

ValidationStatus = Literal["valid", "warnings", "errors"]
DiffStatus = Literal["added", "removed", "modified"]


_DEFAULT_COLLABORATION_TTL_SECONDS = 120
_MIN_COLLABORATION_TTL_SECONDS = 30
_MAX_COLLABORATION_TTL_SECONDS = 3600


class _UnsetType:
    """Sentinel indicating that an optional field was not provided."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - trivial representation
        return "_UNSET"


_UNSET = _UnsetType()


class ExportFormat(str, Enum):
    """Available formatting styles for exported scene JSON."""

    MINIFIED = "minified"
    PRETTY = "pretty"


class CollaboratorRole(str, Enum):
    """Enumerated permission levels for project collaborators."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class ProjectPermissionError(RuntimeError):
    """Raised when a collaborator attempts an unauthorised project mutation."""

    def __init__(self, project_id: str, message: str) -> None:
        super().__init__(message)
        self.project_id = project_id


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


class SceneGraphNodeResource(BaseModel):
    """Node metadata describing a scene within the adventure graph."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus


class SceneGraphEdgeResource(BaseModel):
    """Edge metadata describing a transition between scenes."""

    id: str
    source: str
    command: str
    target: str | None = None
    narration: str
    is_terminal: bool
    item: str | None = None
    requires: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    records: list[str] = Field(default_factory=list)
    failure_narration: str | None = None
    override_count: int = Field(default=0, ge=0)


class SceneGraphResponse(BaseModel):
    """Response payload describing the connectivity graph for scenes."""

    generated_at: datetime
    start_scene: str
    nodes: list[SceneGraphNodeResource] = Field(default_factory=list)
    edges: list[SceneGraphEdgeResource] = Field(default_factory=list)

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


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


class SceneTargetIssueResource(BaseModel):
    """Issue descriptor referencing a command targeting another scene."""

    scene_id: str
    command: str
    target: str


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
    transitions_with_unknown_target: list[SceneTargetIssueResource] = Field(
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


class SceneUpdateRequest(BaseModel):
    """Request payload for updating an existing scene definition."""

    scene: dict[str, Any] = Field(
        ...,
        description="Scene definition matching the export format.",
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version for the uploaded scene. Legacy formats are "
            "migrated automatically when supported."
        ),
    )
    expected_version_id: str | None = Field(
        None,
        description=(
            "Optional optimistic concurrency token derived from the current "
            "dataset version. When provided, updates are rejected if the dataset "
            "has changed."
        ),
    )


class SceneCreateRequest(BaseModel):
    """Request payload for creating a new scene definition."""

    id: str = Field(
        ...,
        description="Identifier for the new scene.",
    )
    scene: dict[str, Any] = Field(
        ...,
        description="Scene definition matching the export format.",
    )
    schema_version: int | None = Field(
        None,
        ge=1,
        description=(
            "Optional schema version for the uploaded scene. Legacy formats are "
            "migrated automatically when supported."
        ),
    )
    expected_version_id: str | None = Field(
        None,
        description=(
            "Optional optimistic concurrency token derived from the current "
            "dataset version. When provided, creation is rejected if the dataset "
            "has changed."
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


class SceneBranchResource(BaseModel):
    """Persisted branch definition metadata returned by the API."""

    id: str = Field(..., description="Stable identifier for the branch definition.")
    name: str = Field(..., description="Display name for the branch definition.")
    created_at: datetime = Field(
        ..., description="Timestamp when the branch definition was saved."
    )
    base: SceneVersionInfo = Field(
        ...,
        description="Metadata describing the base dataset the branch diverges from.",
    )
    target: SceneVersionInfo = Field(
        ..., description="Metadata describing the branch dataset that was saved."
    )
    expected_base_version_id: str | None = Field(
        None,
        description="Version identifier supplied by the client when saving the branch.",
    )
    base_version_matches: bool = Field(
        ...,
        description=(
            "Whether the expected base version matched the bundled dataset when the "
            "branch was saved."
        ),
    )
    summary: SceneDiffSummary = Field(
        ...,
        description="High-level change summary between the base and branch datasets.",
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the branch."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class SceneBranchListResponse(BaseModel):
    """Response envelope describing persisted branch definitions."""

    data: list[SceneBranchResource] = Field(
        default_factory=list,
        description="Collection of saved branch definitions ordered by recency.",
    )


class SceneBranchCreateRequest(SceneBranchPlanRequest):
    """Request payload for persisting a branch definition."""


class SceneBranchDetailResponse(SceneBranchResource):
    """Full branch definition payload including diff metadata and scenes."""

    entries: list[SceneDiffEntry] = Field(
        default_factory=list,
        description="Detailed diff entries between the base and branch datasets.",
    )
    plans: list[SceneImportPlan] = Field(
        default_factory=list,
        description="Import strategies computed when the branch was saved.",
    )
    scenes: dict[str, Any] = Field(
        default_factory=dict,
        description="Scene definitions contained within the saved branch.",
    )


class AdventureProjectResource(BaseModel):
    """Metadata describing an adventure project and its scene dataset."""

    id: str = Field(..., description="Stable identifier for the project.")
    name: str = Field(..., description="Display name for the project.")
    description: str | None = Field(
        None, description="Optional human readable project summary."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the project."
    )
    collaborator_count: int = Field(
        ..., ge=0, description="Number of collaborators with access to the project."
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the project metadata was last updated."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the scene dataset was last updated."
    )
    version_id: str = Field(
        ...,
        description="Version identifier derived from the dataset timestamp and checksum.",
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the serialised scene dataset."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class AdventureProjectListResponse(BaseModel):
    """Response envelope describing available adventure projects."""

    data: list[AdventureProjectResource] = Field(
        default_factory=list,
        description="Collection of registered projects ordered by identifier.",
    )


class AdventureProjectTemplateResource(BaseModel):
    """Metadata describing an adventure project template."""

    id: str = Field(..., description="Stable identifier for the template.")
    name: str = Field(..., description="Display name for the template.")
    description: str | None = Field(
        None, description="Optional summary of the template adventure."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the template."
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the template metadata was last updated."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the template dataset was last updated."
    )
    version_id: str = Field(
        ...,
        description="Version identifier derived from the template timestamp and checksum.",
    )
    checksum: str = Field(
        ..., description="SHA-256 checksum of the serialised template scene dataset."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class AdventureProjectTemplateListResponse(BaseModel):
    """Response envelope describing available project templates."""

    data: list[AdventureProjectTemplateResource] = Field(
        default_factory=list,
        description="Collection of registered project templates ordered by identifier.",
    )


class MarketplaceEntrySummary(BaseModel):
    """Summary metadata describing a published marketplace entry."""

    id: str = Field(..., description="Stable identifier for the marketplace entry.")
    title: str = Field(..., description="Display title for the shared adventure.")
    description: str | None = Field(
        None,
        description="Optional short description supplied by the publisher.",
    )
    author: str | None = Field(
        None,
        description="Optional credit or author name provided by the publisher.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Normalised discovery tags associated with the entry.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the entry was published."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the entry."
    )
    average_rating: float | None = Field(
        None,
        ge=1.0,
        le=5.0,
        description="Average rating for the entry if any reviews have been submitted.",
    )
    review_count: int = Field(
        0,
        ge=0,
        description="Number of reviews that have been recorded for the entry.",
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class MarketplaceReview(BaseModel):
    """Representation of a marketplace review visible through the API."""

    reviewer: str | None = Field(
        None,
        description="Optional reviewer name supplied alongside the rating.",
    )
    rating: int = Field(..., ge=1, le=5, description="Rating value between 1 and 5.")
    comment: str | None = Field(
        None,
        description="Optional free-form feedback accompanying the rating.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp describing when the review was submitted."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class MarketplaceEntryResponse(MarketplaceEntrySummary):
    """Full representation of a published marketplace entry."""

    schema_version: int = Field(
        ..., description="Scene schema version the bundled dataset adheres to."
    )
    scenes: dict[str, Any] = Field(
        default_factory=dict,
        description="Scene definitions that make up the shared adventure.",
    )
    reviews: list[MarketplaceReview] = Field(
        default_factory=list,
        description="Collection of reviews that have been submitted for the entry.",
    )


class MarketplaceEntryListResponse(BaseModel):
    """Response envelope describing marketplace entries."""

    data: list[MarketplaceEntrySummary] = Field(
        default_factory=list,
        description="Collection of marketplace entries ordered by recency.",
    )
    pagination: Pagination


class MarketplaceReviewCreateRequest(BaseModel):
    """Request payload for submitting a review for a marketplace entry."""

    reviewer: str | None = Field(
        None,
        description="Optional reviewer name that will be displayed alongside the review.",
    )
    rating: int = Field(..., ge=1, le=5, description="Rating value between 1 and 5.")
    comment: str | None = Field(
        None,
        description="Optional free-form comment providing additional feedback.",
    )

    @field_validator("reviewer", "comment", mode="before")
    @classmethod
    def _normalise_optional_text_field(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        raise TypeError("Value must be a string or null.")


class MarketplaceReviewListResponse(BaseModel):
    """Response envelope describing reviews for a marketplace entry."""

    data: list[MarketplaceReview] = Field(
        default_factory=list,
        description="Collection of reviews ordered by submission time (newest first).",
    )
    average_rating: float | None = Field(
        None,
        ge=1.0,
        le=5.0,
        description="Average rating across all submitted reviews.",
    )
    review_count: int = Field(
        0,
        ge=0,
        description="Number of reviews that have been submitted.",
    )


class ForumPostResource(BaseModel):
    """Representation of a post within a forum thread exposed via the API."""

    id: str = Field(..., description="Stable identifier for the forum post.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the post author.",
    )
    body: str = Field(..., description="Rendered message content for the post.")
    created_at: datetime = Field(
        ..., description="Timestamp describing when the post was created."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class ForumThreadSummary(BaseModel):
    """Lightweight overview of a forum discussion thread."""

    id: str = Field(..., description="Stable identifier for the forum thread.")
    title: str = Field(..., description="Title describing the discussion topic.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the thread creator.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the thread was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp of the most recent activity within the thread."
    )
    post_count: int = Field(
        ...,
        ge=0,
        description="Number of posts currently recorded for the thread.",
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class ForumThreadDetail(ForumThreadSummary):
    """Detailed representation of a forum thread including individual posts."""

    posts: list[ForumPostResource] = Field(
        default_factory=list,
        description="Collection of posts ordered chronologically within the thread.",
    )


class ForumThreadListResponse(BaseModel):
    """Response envelope describing paginated forum threads."""

    data: list[ForumThreadSummary] = Field(
        default_factory=list,
        description="Collection of forum threads ordered by recent activity.",
    )
    pagination: Pagination


class ForumThreadCreateRequest(BaseModel):
    """Request payload for creating a new forum discussion thread."""

    title: str = Field(..., description="Title describing the discussion topic.")
    body: str = Field(..., description="Initial post content for the new thread.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the thread creator.",
    )
    identifier: str | None = Field(
        None,
        description="Optional custom identifier for the thread. Slugified when provided.",
    )

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Thread title must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Thread title must be a non-empty string.")
        return trimmed

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Thread body must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Thread body must be a non-empty string.")
        return trimmed

    @field_validator("author", mode="before")
    @classmethod
    def _normalise_author(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        raise TypeError("Author must be a string or null.")

    @field_validator("identifier")
    @classmethod
    def _validate_identifier(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TypeError("Thread identifier must be provided as a string.")
        return _normalise_forum_identifier(value)


class ForumPostCreateRequest(BaseModel):
    """Request payload for adding a reply to an existing forum thread."""

    body: str = Field(..., description="Content of the reply post.")
    author: str | None = Field(
        None,
        description="Optional display name associated with the post author.",
    )

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("Post body must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Post body must be a non-empty string.")
        return trimmed

    @field_validator("author", mode="before")
    @classmethod
    def _normalise_author(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            trimmed = value.strip()
            return trimmed or None
        raise TypeError("Author must be a string or null.")


class MarketplaceEntryPublishRequest(BaseModel):
    """Request payload for publishing an adventure to the marketplace."""

    identifier: str | None = Field(
        None,
        description=(
            "Optional identifier to assign to the entry. If omitted, an identifier "
            "is generated from the title."
        ),
    )
    title: str = Field(..., description="Display title for the shared adventure.")
    description: str | None = Field(
        None, description="Optional short description of the adventure."
    )
    author: str | None = Field(
        None, description="Optional credit or author name for the adventure."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional discovery tags to associate with the entry.",
    )
    scenes: Mapping[str, Any] = Field(
        ...,
        description=(
            "Scene definitions that should be bundled with the marketplace entry."
        ),
    )
    schema_version: int = Field(
        ..., ge=1, description="Scene schema version describing the dataset."
    )

    @field_validator("identifier")
    @classmethod
    def _normalise_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalise_marketplace_identifier(value)

    @field_validator("title")
    @classmethod
    def _normalise_title(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Title must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Title must be a non-empty string.")
        return trimmed

    @field_validator("description")
    @classmethod
    def _normalise_description(cls, value: str | None) -> str | None:
        return _normalise_optional_text(value)

    @field_validator("author")
    @classmethod
    def _normalise_author(cls, value: str | None) -> str | None:
        return _normalise_optional_text(value)

    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, value: Sequence[str]) -> list[str]:
        if isinstance(value, str):
            raise ValueError("Tags must be provided as an iterable of strings.")
        if value is None:
            return []
        seen: set[str] = set()
        normalised: list[str] = []
        for tag in value:
            if not isinstance(tag, str):
                raise ValueError("Tags must be provided as strings.")
            candidate = _normalise_optional_text(tag) or ""
            if not candidate:
                continue
            slug = candidate.casefold()
            if slug in seen:
                continue
            seen.add(slug)
            normalised.append(slug)
        return normalised

    @field_validator("scenes")
    @classmethod
    def _validate_scenes(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("Scenes must be provided as a mapping.")
        return value

    @model_validator(mode="after")
    def _validate_schema_version(self) -> "MarketplaceEntryPublishRequest":
        if self.schema_version != CURRENT_SCENE_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must match the current scene schema version."
            )
        return self


class ProjectTemplateInstantiateRequest(BaseModel):
    """Request payload for instantiating a project template."""

    project_id: str = Field(..., description="Identifier to assign to the new project.")
    name: str | None = Field(
        None,
        description="Optional display name to persist for the newly created project.",
    )
    description: str | None = Field(
        None, description="Optional summary describing the newly created project."
    )


class AdventureProjectDetailResponse(BaseModel):
    """Full project payload including the bundled scene dataset."""

    data: AdventureProjectResource = Field(
        ..., description="Metadata describing the requested project."
    )
    scenes: dict[str, Any] = Field(
        default_factory=dict,
        description="Scene definitions contained within the project dataset.",
    )


class ProjectAssetType(str, Enum):
    """Enumerated asset kinds surfaced by the project API."""

    FILE = "file"
    DIRECTORY = "directory"


class ProjectAssetResource(BaseModel):
    """Metadata describing an individual asset within a project."""

    path: str = Field(
        ..., description="Path relative to the project's assets directory."
    )
    name: str = Field(..., description="Basename of the asset entry.")
    type: ProjectAssetType = Field(
        ..., description="Indicates whether the entry is a file or directory."
    )
    size: int | None = Field(
        default=None,
        ge=0,
        description="File size in bytes when the asset is a file.",
    )
    content_type: str | None = Field(
        default=None,
        description="Best-effort MIME type derived from the filename.",
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the asset was last modified."
    )

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class ProjectAssetListResponse(BaseModel):
    """Response payload enumerating assets registered under a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    root: str = Field(
        ..., description="Directory anchoring asset lookups for the project."
    )
    generated_at: datetime = Field(
        ..., description="Timestamp when the asset listing was generated."
    )
    assets: list[ProjectAssetResource] = Field(
        default_factory=list, description="Ordered collection of project assets."
    )

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


@dataclass(frozen=True)
class ProjectAssetContent:
    """Binary payload representing an asset stored alongside a project."""

    filename: str
    content: bytes
    content_type: str | None


@dataclass(frozen=True)
class ProjectExportArchive:
    """ZIP archive containing a project's dataset, metadata, and assets."""

    project_id: str
    filename: str
    content: bytes
    content_type: str
    size: int
    generated_at: datetime
    version_id: str
    checksum: str


class ProjectAssetUploadRequest(BaseModel):
    """Payload describing the contents of an uploaded project asset."""

    content: str = Field(
        ..., description="Base64-encoded binary payload for the asset."
    )

    @field_validator("content")
    @classmethod
    def _validate_content(cls, value: str) -> str:
        try:
            base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "Asset content must be provided as base64-encoded data."
            ) from exc
        return value

    def decoded_content(self) -> bytes:
        return base64.b64decode(self.content)


class BinaryResponse:
    """Minimal response object for returning binary payloads in tests."""

    def __init__(
        self,
        *,
        content: bytes,
        media_type: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.body = content
        self.media_type = media_type
        self.headers = dict(headers or {})


class ProjectCollaboratorResource(BaseModel):
    """Representation of a collaborator's access level for a project."""

    user_id: str = Field(
        ..., description="Unique identifier for the collaborator (e.g. email)."
    )
    role: CollaboratorRole = Field(
        ..., description="Permission level granted to the collaborator."
    )
    display_name: str | None = Field(
        None,
        description="Optional human readable label for the collaborator.",
    )

    @field_validator("user_id")
    @classmethod
    def _validate_user_id(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Collaborator user_id must not be empty.")
        return trimmed

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ProjectCollaboratorListResponse(BaseModel):
    """Response payload enumerating collaborators for a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    collaborators: list[ProjectCollaboratorResource] = Field(
        default_factory=list,
        description="Ordered list of collaborators with access to the project.",
    )


class ProjectCollaboratorUpdateRequest(BaseModel):
    """Request body for replacing a project's collaborator roster."""

    collaborators: list[ProjectCollaboratorResource] = Field(
        default_factory=list,
        description="Complete collaborator list to persist for the project.",
    )


class ProjectCollaborationSessionResource(BaseModel):
    """Active collaboration session metadata exposed via the API."""

    session_id: str = Field(
        ..., description="Unique identifier representing the collaboration session."
    )
    user_id: str = Field(
        ..., description="Identifier of the collaborator associated with the session."
    )
    role: CollaboratorRole = Field(
        ..., description="Permission level granted to the collaborator."
    )
    display_name: str | None = Field(
        None, description="Optional display name resolved for the collaborator."
    )
    scene_id: str | None = Field(
        None,
        description="Optional scene identifier the collaborator is currently editing.",
    )
    started_at: datetime = Field(
        ..., description="Timestamp indicating when the session was created."
    )
    last_heartbeat: datetime = Field(
        ..., description="Timestamp for the most recent heartbeat received."
    )
    expires_at: datetime = Field(
        ..., description="Timestamp when the session will automatically expire."
    )

    @field_serializer("started_at")
    def _serialise_started_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("last_heartbeat")
    def _serialise_last_heartbeat(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("expires_at")
    def _serialise_expires_at(self, value: datetime) -> str:
        return value.isoformat()


class ProjectCollaborationSessionListResponse(BaseModel):
    """Response payload listing active collaboration sessions for a project."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    sessions: list[ProjectCollaborationSessionResource] = Field(
        default_factory=list,
        description="Collection of active collaboration sessions.",
    )


class ProjectCollaborationSessionRequest(BaseModel):
    """Request body for joining or heartbeating a collaboration session."""

    session_id: str | None = Field(
        None,
        description="Existing session identifier to refresh. Omit to create a new session.",
    )
    scene_id: str | None = Field(
        None,
        description="Optional scene identifier describing the collaborator's focus.",
    )
    ttl_seconds: int | None = Field(
        None,
        ge=_MIN_COLLABORATION_TTL_SECONDS,
        le=_MAX_COLLABORATION_TTL_SECONDS,
        description=(
            "Requested inactivity timeout in seconds before the session expires."
        ),
    )


class UserProfileResource(BaseModel):
    """Representation of a user account exposed through the API."""

    id: str = Field(..., description="Stable identifier for the user profile.")
    display_name: str = Field(
        ..., description="Human readable label to present in user interfaces."
    )
    email: str | None = Field(
        None, description="Optional contact email address associated with the user."
    )
    bio: str | None = Field(
        None, description="Optional free-form biography or profile summary."
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the profile was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp indicating when the profile was last updated."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()


class UserProfileListResponse(BaseModel):
    """Response envelope listing registered user profiles."""

    data: list[UserProfileResource] = Field(
        default_factory=list,
        description="Collection of user profiles ordered by identifier.",
    )


class UserProfileCreateRequest(BaseModel):
    """Request payload for creating a new user profile."""

    id: str = Field(..., description="Identifier to persist for the new profile.")
    display_name: str = Field(
        ..., description="Human readable name to associate with the profile."
    )
    email: str | None = Field(
        None, description="Optional contact email address for the profile."
    )
    bio: str | None = Field(
        None, description="Optional free-form biography to associate with the user."
    )

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must be a non-empty string.")
        return trimmed

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if "@" not in trimmed:
            raise ValueError("Email address must contain an '@' symbol.")
        return trimmed

    @field_validator("bio")
    @classmethod
    def _normalise_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class UserProfileUpdateRequest(BaseModel):
    """Request payload for updating an existing user profile."""

    display_name: str | None = Field(
        None,
        description="Optional replacement for the human readable profile name.",
    )
    email: str | None = Field(
        None, description="Optional replacement contact email for the profile."
    )
    bio: str | None = Field(
        None, description="Optional replacement biography to persist for the user."
    )

    @field_validator("display_name")
    @classmethod
    def _normalise_display_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Display name cannot be null when provided.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Display name must be a non-empty string when provided.")
        return trimmed

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if "@" not in trimmed:
            raise ValueError("Email address must contain an '@' symbol.")
        return trimmed

    @field_validator("bio")
    @classmethod
    def _normalise_bio(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def _ensure_fields_provided(self) -> "UserProfileUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided to update a profile.")
        return self


@dataclass(frozen=True)
class SceneBranchRecord:
    """Representation of a branch definition stored on disk."""

    identifier: str
    name: str
    created_at: datetime
    plan: SceneBranchPlanResponse
    scenes: dict[str, Any]


class SceneBranchStore:
    """Filesystem-backed store for persisted branch definitions."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path.cwd() / "scene_branches"

    def list(self) -> list[SceneBranchRecord]:
        """Return all stored branch definitions ordered by recency."""

        if not self._root.exists():
            return []

        records: list[SceneBranchRecord] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                payload = _load_json(path)
            except (ValueError, OSError) as exc:
                raise ValueError(
                    f"Failed to load branch definition from '{path}'."
                ) from exc

            try:
                record = self._record_from_payload(payload, path)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            records.append(record)

        records.sort(key=lambda record: record.created_at, reverse=True)
        return records

    def load(self, identifier: str) -> SceneBranchRecord:
        """Return the stored branch definition identified by ``identifier``."""

        path = self._path_for(identifier)
        if not path.exists():
            raise FileNotFoundError(f"Branch '{identifier}' does not exist.")

        try:
            payload = _load_json(path)
        except (ValueError, OSError) as exc:
            raise ValueError(
                f"Failed to load branch definition from '{path}'."
            ) from exc

        try:
            return self._record_from_payload(payload, path)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    def save(self, record: SceneBranchRecord) -> None:
        """Persist ``record`` to disk, ensuring identifiers remain unique."""

        path = self._path_for(record.identifier)
        if path.exists():
            raise FileExistsError(f"Branch '{record.identifier}' already exists.")

        payload = {
            "id": record.identifier,
            "name": record.name,
            "created_at": record.created_at.isoformat(),
            "plan": record.plan.model_dump(mode="json"),
            "scenes": record.scenes,
        }

        try:
            serialisable = json.loads(json.dumps(payload, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("Branch data could not be serialised to JSON.") from exc

        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(serialisable, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError("Failed to persist branch definition.") from exc

    def delete(self, identifier: str) -> None:
        """Remove the stored branch definition identified by ``identifier``."""

        path = self._path_for(identifier)
        if not path.exists():
            raise FileNotFoundError(f"Branch '{identifier}' does not exist.")

        try:
            path.unlink()
        except OSError as exc:
            raise RuntimeError("Failed to delete branch definition.") from exc

    def _record_from_payload(self, payload: Any, path: Path) -> SceneBranchRecord:
        if not isinstance(payload, Mapping):
            raise ValueError(f"Branch data in '{path}' is invalid.")

        try:
            identifier = str(payload["id"])
            name = str(payload.get("name", identifier))
            created_at_raw = payload["created_at"]
            plan_payload = payload["plan"]
            scenes_payload = payload["scenes"]
        except KeyError as exc:
            raise ValueError(f"Branch data in '{path}' is invalid.") from exc

        try:
            created_at = _ensure_timezone(datetime.fromisoformat(created_at_raw))
        except ValueError as exc:
            raise ValueError(f"Branch timestamp in '{path}' is invalid.") from exc

        try:
            plan = SceneBranchPlanResponse.model_validate(plan_payload)
        except ValidationError as exc:
            raise ValueError(f"Branch metadata in '{path}' is invalid.") from exc

        if not isinstance(scenes_payload, Mapping):
            raise ValueError(f"Branch scenes in '{path}' must be a mapping.")

        try:
            serialisable_scenes = json.loads(
                json.dumps(scenes_payload, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Branch scenes in '{path}' could not be serialised to JSON."
            ) from exc

        return SceneBranchRecord(
            identifier=identifier,
            name=name,
            created_at=created_at,
            plan=plan,
            scenes=cast(dict[str, Any], serialisable_scenes),
        )

    def _path_for(self, identifier: str) -> Path:
        return self._root / f"{identifier}.json"


@dataclass(frozen=True)
class ProjectCollaboratorRecord:
    """Internal representation of a collaborator entry stored on disk."""

    user_id: str
    role: CollaboratorRole
    display_name: str | None


@dataclass(frozen=True)
class ProjectCollaborationSessionRecord:
    """Ephemeral collaboration session metadata stored on disk."""

    session_id: str
    user_id: str
    scene_id: str | None
    started_at: datetime
    last_heartbeat: datetime
    expires_at: datetime


@dataclass(frozen=True)
class UserAccountRecord:
    """Filesystem-backed representation of a user profile."""

    identifier: str
    display_name: str
    email: str | None
    bio: str | None
    created_at: datetime
    updated_at: datetime
    path: Path


@dataclass(frozen=True)
class AdventureProjectRecord:
    """Representation of a project definition stored on disk."""

    identifier: str
    name: str
    description: str | None
    scene_path: Path
    created_at: datetime
    updated_at: datetime
    metadata_path: Path
    collaborators: tuple[ProjectCollaboratorRecord, ...]


class SceneProjectStore:
    """Filesystem-backed registry for adventure projects."""

    _METADATA_FILENAME = "project.json"
    _DEFAULT_DATASET_NAME = "scenes.json"
    _COLLABORATION_FILENAME = "collaboration.json"

    def __init__(self, root: Path) -> None:
        self._root = root

    def list(self) -> list[AdventureProjectRecord]:
        """Return all registered projects ordered by identifier."""

        if not self._root.exists():
            return []

        records: list[AdventureProjectRecord] = []
        for entry in sorted(self._root.iterdir(), key=lambda path: path.name):
            if not entry.is_dir():
                continue
            records.append(self._record_from_directory(entry))

        return records

    def load(self, identifier: str) -> AdventureProjectRecord:
        """Return the project definition identified by ``identifier``."""

        if not identifier:
            raise ValueError("Project identifier must be provided.")

        directory = self._root / identifier
        if not directory.is_dir():
            raise FileNotFoundError(f"Project '{identifier}' does not exist.")

        return self._record_from_directory(directory, identifier_override=identifier)

    def export_archive(self, identifier: str) -> ProjectExportArchive:
        """Package the full project directory into a ZIP archive."""

        if not isinstance(identifier, str):
            raise ValueError("Project identifier must be provided as a string.")

        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        record = self.load(trimmed_identifier)
        _, checksum, version_id = _load_project_dataset(record)

        project_root = record.scene_path.parent
        generated_at = datetime.now(timezone.utc)

        buffer = io.BytesIO()
        root_prefix = f"{record.identifier}/"

        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(root_prefix, b"")

            for dirpath, dirnames, filenames in os.walk(project_root):
                dirnames.sort()
                filenames.sort()

                current_dir = Path(dirpath)
                relative_dir = current_dir.relative_to(project_root)

                if relative_dir == Path("."):
                    dir_prefix = ""
                else:
                    dir_prefix = f"{relative_dir.as_posix()}/"
                    archive.writestr(f"{root_prefix}{dir_prefix}", b"")

                for filename in filenames:
                    file_path = current_dir / filename
                    arcname = f"{root_prefix}{dir_prefix}{filename}"
                    archive.write(file_path, arcname=arcname)

        content = buffer.getvalue()

        filename = f"{record.identifier}-project-export-{version_id}.zip"
        return ProjectExportArchive(
            project_id=record.identifier,
            filename=filename,
            content=content,
            content_type="application/zip",
            size=len(content),
            generated_at=generated_at,
            version_id=version_id,
            checksum=checksum,
        )

    def create(
        self,
        *,
        identifier: str,
        scenes: Mapping[str, Any],
        name: str | None = None,
        description: str | None = None,
        scene_filename: str | None = None,
        collaborators: Sequence[ProjectCollaboratorRecord] | None = None,
    ) -> AdventureProjectRecord:
        """Create a new project directory populated with ``scenes``."""

        normalised_id = _normalise_project_identifier(identifier)
        dataset_name = (
            _validate_scene_filename(scene_filename)
            if scene_filename is not None
            else self._DEFAULT_DATASET_NAME
        )

        metadata_payload: dict[str, Any] = {}
        collaborator_records: tuple[ProjectCollaboratorRecord, ...] = (
            _ensure_unique_collaborators(collaborators, normalised_id)
            if collaborators is not None
            else ()
        )

        if name is not None:
            if not isinstance(name, str):
                raise ValueError("Project name must be provided as a string.")
            trimmed_name = name.strip()
            if not trimmed_name:
                raise ValueError(
                    "Project name must be a non-empty string when provided."
                )
            metadata_payload["name"] = trimmed_name

        if description is not None:
            if not isinstance(description, str):
                raise ValueError("Project description must be provided as a string.")
            metadata_payload["description"] = description

        if dataset_name != self._DEFAULT_DATASET_NAME:
            metadata_payload["scene_path"] = dataset_name

        if collaborator_records:
            metadata_payload["collaborators"] = _serialise_collaborators(
                collaborator_records
            )

        serialisable = _ensure_serialisable_scene_mapping(scenes)

        directory = self._root / normalised_id
        try:
            directory.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise FileExistsError(f"Project '{normalised_id}' already exists.") from exc
        except OSError as exc:
            raise RuntimeError(
                f"Failed to create project directory '{directory}'."
            ) from exc

        dataset_path = directory / dataset_name
        try:
            with dataset_path.open("w", encoding="utf-8") as handle:
                json.dump(serialisable, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write scene dataset for project '{normalised_id}'."
            ) from exc

        if metadata_payload:
            metadata_path = directory / self._METADATA_FILENAME
            self._write_metadata_payload(
                metadata_path,
                metadata_payload,
                project_id=normalised_id,
            )

        assets_directory = directory / "assets"
        try:
            assets_directory.mkdir(exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare assets directory for project '{normalised_id}'."
            ) from exc

        return self._record_from_directory(directory, identifier_override=normalised_id)

    def _record_from_directory(
        self, directory: Path, *, identifier_override: str | None = None
    ) -> AdventureProjectRecord:
        metadata_path = directory / self._METADATA_FILENAME
        metadata = self._load_metadata_payload(metadata_path)
        identifier = identifier_override or directory.name
        name_raw = metadata.get("name")
        description_raw = metadata.get("description")
        scene_name_raw = metadata.get("scene_path", self._DEFAULT_DATASET_NAME)

        if name_raw is None:
            name = identifier
        elif isinstance(name_raw, str) and name_raw.strip():
            name = name_raw
        else:
            raise ValueError(
                f"Project '{identifier}' metadata has an invalid 'name' field."
            )

        if description_raw is None:
            description: str | None = None
        elif isinstance(description_raw, str):
            description = description_raw
        else:
            raise ValueError(
                f"Project '{identifier}' metadata has an invalid 'description' field."
            )

        if not isinstance(scene_name_raw, str) or not scene_name_raw.strip():
            raise ValueError(
                f"Project '{identifier}' metadata has an invalid 'scene_path' field."
            )

        scene_path = directory / scene_name_raw
        if not scene_path.exists():
            raise FileNotFoundError(
                f"Project '{identifier}' is missing scene dataset '{scene_name_raw}'."
            )

        collaborators = _parse_collaborators(
            metadata.get("collaborators"), project_id=identifier
        )

        dataset_timestamp = _timestamp_for(scene_path)
        metadata_timestamp = (
            _timestamp_for(metadata_path)
            if metadata_path.exists()
            else dataset_timestamp
        )

        created_at = min(metadata_timestamp, dataset_timestamp)

        return AdventureProjectRecord(
            identifier=identifier,
            name=name,
            description=description,
            scene_path=scene_path,
            created_at=created_at,
            updated_at=dataset_timestamp,
            metadata_path=metadata_path,
            collaborators=collaborators,
        )

    def replace_collaborators(
        self,
        identifier: str,
        collaborators: Sequence[ProjectCollaboratorRecord],
    ) -> AdventureProjectRecord:
        if not isinstance(identifier, str):
            raise ValueError("Project identifier must be provided as a string.")

        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be a non-empty string.")

        record = self.load(trimmed_identifier)
        validated = _ensure_unique_collaborators(collaborators, record.identifier)

        metadata = self._load_metadata_payload(record.metadata_path)
        payload: dict[str, Any] = dict(metadata)
        payload["name"] = record.name

        if record.description is not None:
            payload["description"] = record.description
        else:
            payload.pop("description", None)

        payload["scene_path"] = record.scene_path.name

        if validated:
            payload["collaborators"] = _serialise_collaborators(validated)
        else:
            payload.pop("collaborators", None)

        self._write_metadata_payload(
            record.metadata_path,
            payload,
            project_id=record.identifier,
        )

        return self._record_from_directory(
            record.scene_path.parent, identifier_override=record.identifier
        )

    def load_collaboration_sessions(
        self, record: AdventureProjectRecord
    ) -> tuple[ProjectCollaborationSessionRecord, ...]:
        """Return persisted collaboration sessions for ``record``."""

        path = record.scene_path.parent / self._COLLABORATION_FILENAME
        sessions = self._read_collaboration_sessions(path, record.identifier)
        return tuple(sessions)

    def save_collaboration_sessions(
        self,
        record: AdventureProjectRecord,
        sessions: Sequence[ProjectCollaborationSessionRecord],
    ) -> tuple[ProjectCollaborationSessionRecord, ...]:
        """Persist collaboration sessions for ``record`` and return the stored set."""

        path = record.scene_path.parent / self._COLLABORATION_FILENAME
        self._write_collaboration_sessions(path, sessions, record.identifier)
        return tuple(sessions)

    def _load_metadata_payload(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}

        try:
            payload = _load_json(path)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Failed to load project metadata from '{path}'.") from exc

        if not isinstance(payload, Mapping):
            raise ValueError(f"Project metadata in '{path}' must be a mapping.")

        return dict(payload)

    def _write_metadata_payload(
        self,
        path: Path,
        payload: Mapping[str, Any],
        *,
        project_id: str,
    ) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare metadata directory for '{project_id}'."
            ) from exc

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write project metadata for '{project_id}'."
            ) from exc

    def _read_collaboration_sessions(
        self, path: Path, project_id: str
    ) -> List[ProjectCollaborationSessionRecord]:
        if not path.exists():
            return []

        try:
            payload = _load_json(path)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Project '{project_id}' collaboration metadata could not be loaded."
            ) from exc

        if not isinstance(payload, Mapping):
            raise ValueError(
                f"Project '{project_id}' collaboration metadata must be a mapping."
            )

        raw_sessions = payload.get("sessions", [])
        if raw_sessions is None:
            return []
        if not isinstance(raw_sessions, Sequence):
            raise ValueError(
                f"Project '{project_id}' collaboration metadata has an invalid 'sessions' field."
            )

        sessions: list[ProjectCollaborationSessionRecord] = []
        seen_ids: set[str] = set()

        for index, entry in enumerate(raw_sessions):
            if not isinstance(entry, Mapping):
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "must be a mapping."
                    )
                )

            session_id_raw = entry.get("session_id")
            user_id_raw = entry.get("user_id")
            scene_id_raw = entry.get("scene_id")
            started_at_raw = entry.get("started_at")
            heartbeat_raw = entry.get("last_heartbeat")
            expires_at_raw = entry.get("expires_at")

            if not isinstance(session_id_raw, str):
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "is missing a valid 'session_id'."
                    )
                )
            if not isinstance(user_id_raw, str):
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "is missing a valid 'user_id'."
                    )
                )
            if (
                not isinstance(started_at_raw, str)
                or not isinstance(heartbeat_raw, str)
                or not isinstance(expires_at_raw, str)
            ):
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "has invalid timestamp fields."
                    )
                )

            session_id = session_id_raw.strip()
            user_id = user_id_raw.strip()

            if not session_id:
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "must include a non-empty 'session_id'."
                    )
                )
            if not user_id:
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session at index {index} "
                        "must include a non-empty 'user_id'."
                    )
                )
            if session_id in seen_ids:
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration metadata defines duplicate "
                        f"session id '{session_id}'."
                    )
                )
            seen_ids.add(session_id)

            scene_id: str | None
            if scene_id_raw is None:
                scene_id = None
            elif isinstance(scene_id_raw, str):
                trimmed_scene = scene_id_raw.strip()
                scene_id = trimmed_scene or None
            else:
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session '{session_id}' "
                        "has an invalid 'scene_id'."
                    )
                )

            try:
                started_at = _ensure_timezone(datetime.fromisoformat(started_at_raw))
                last_heartbeat = _ensure_timezone(datetime.fromisoformat(heartbeat_raw))
                expires_at = _ensure_timezone(datetime.fromisoformat(expires_at_raw))
            except ValueError as exc:
                raise ValueError(
                    (
                        f"Project '{project_id}' collaboration session '{session_id}' "
                        "contains invalid timestamps."
                    )
                ) from exc

            sessions.append(
                ProjectCollaborationSessionRecord(
                    session_id=session_id,
                    user_id=user_id,
                    scene_id=scene_id,
                    started_at=started_at,
                    last_heartbeat=last_heartbeat,
                    expires_at=expires_at,
                )
            )

        return sessions

    def _write_collaboration_sessions(
        self,
        path: Path,
        sessions: Sequence[ProjectCollaborationSessionRecord],
        project_id: str,
    ) -> None:
        payload = {
            "sessions": [
                {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "scene_id": session.scene_id,
                    "started_at": session.started_at.isoformat(),
                    "last_heartbeat": session.last_heartbeat.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                }
                for session in sessions
            ]
        }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare collaboration metadata for project '{project_id}'."
            ) from exc

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write collaboration metadata for project '{project_id}'."
            ) from exc


class UserAccountStore:
    """Filesystem-backed registry for user profile data."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def list(self) -> list[UserAccountRecord]:
        """Return all stored user profiles ordered by identifier."""

        if not self._root.exists():
            return []

        records: list[UserAccountRecord] = []
        for entry in sorted(self._root.glob("*.json"), key=lambda path: path.name):
            if not entry.is_file():
                continue
            records.append(self._record_from_file(entry))

        return records

    def load(self, identifier: str) -> UserAccountRecord:
        """Return the user profile identified by ``identifier``."""

        normalised = _normalise_user_identifier(identifier)
        path = self._path_for(normalised)
        if not path.exists():
            raise FileNotFoundError(f"User '{normalised}' does not exist.")

        return self._record_from_file(path)

    def create(
        self,
        *,
        identifier: str,
        display_name: str,
        email: str | None = None,
        bio: str | None = None,
    ) -> UserAccountRecord:
        """Persist a new user profile."""

        normalised = _normalise_user_identifier(identifier)
        validated_display_name = _validate_display_name(display_name)
        validated_email = _normalise_optional_email(email)
        validated_bio = _normalise_optional_text(bio)

        path = self._path_for(normalised)
        if path.exists():
            raise FileExistsError(f"User '{normalised}' already exists.")

        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "id": normalised,
            "display_name": validated_display_name,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        if validated_email is not None:
            payload["email"] = validated_email
        if validated_bio is not None:
            payload["bio"] = validated_bio

        self._write_payload(path, payload, identifier=normalised)

        return UserAccountRecord(
            identifier=normalised,
            display_name=validated_display_name,
            email=validated_email,
            bio=validated_bio,
            created_at=now,
            updated_at=now,
            path=path,
        )

    def update(
        self,
        identifier: str,
        *,
        display_name: str | _UnsetType | None = _UNSET,
        email: str | _UnsetType | None = _UNSET,
        bio: str | _UnsetType | None = _UNSET,
    ) -> UserAccountRecord:
        """Persist field updates for an existing user profile."""

        record = self.load(identifier)

        updated_display = record.display_name
        if not isinstance(display_name, _UnsetType):
            if display_name is None:
                raise ValueError("Display name cannot be removed from a user profile.")
            updated_display = _validate_display_name(display_name)

        updated_email = record.email
        if not isinstance(email, _UnsetType):
            updated_email = _normalise_optional_email(email)

        updated_bio = record.bio
        if not isinstance(bio, _UnsetType):
            updated_bio = _normalise_optional_text(bio)

        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "id": record.identifier,
            "display_name": updated_display,
            "created_at": record.created_at.isoformat(),
            "updated_at": now.isoformat(),
        }
        if updated_email is not None:
            payload["email"] = updated_email
        if updated_bio is not None:
            payload["bio"] = updated_bio

        self._write_payload(record.path, payload, identifier=record.identifier)

        return UserAccountRecord(
            identifier=record.identifier,
            display_name=updated_display,
            email=updated_email,
            bio=updated_bio,
            created_at=record.created_at,
            updated_at=now,
            path=record.path,
        )

    def _record_from_file(self, path: Path) -> UserAccountRecord:
        try:
            payload = _load_json(path)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Failed to load user profile from '{path}'.") from exc

        if not isinstance(payload, Mapping):
            raise ValueError(f"User profile in '{path}' must be a mapping.")

        try:
            identifier_raw = payload["id"]
            display_name_raw = payload["display_name"]
        except KeyError as exc:
            raise ValueError(
                f"User profile in '{path}' is missing required fields."
            ) from exc

        if not isinstance(identifier_raw, str):
            raise ValueError(f"User profile in '{path}' has an invalid 'id' field.")
        if not isinstance(display_name_raw, str):
            raise ValueError(
                f"User profile in '{path}' has an invalid 'display_name' field."
            )

        identifier = _normalise_user_identifier(identifier_raw)
        display_name = _validate_display_name(display_name_raw)
        email = _normalise_optional_email(payload.get("email"))
        bio = _normalise_optional_text(payload.get("bio"))

        created_at = self._parse_timestamp(
            payload.get("created_at"), path, "created_at"
        )
        updated_at = self._parse_timestamp(
            payload.get("updated_at"), path, "updated_at"
        )

        return UserAccountRecord(
            identifier=identifier,
            display_name=display_name,
            email=email,
            bio=bio,
            created_at=created_at,
            updated_at=updated_at,
            path=path,
        )

    def _parse_timestamp(self, value: Any, path: Path, field: str) -> datetime:
        if not isinstance(value, str):
            raise ValueError(
                f"User profile in '{path}' has an invalid '{field}' field."
            )

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"User profile in '{path}' has an invalid '{field}' field."
            ) from exc

        return _ensure_timezone(parsed)

    def _write_payload(
        self, path: Path, payload: Mapping[str, Any], *, identifier: str
    ) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare directory for user '{identifier}'."
            ) from exc

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(dict(payload), handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write user profile for '{identifier}'."
            ) from exc

    def _path_for(self, identifier: str) -> Path:
        return self._root / f"{identifier}.json"


@dataclass(frozen=True)
class MarketplaceReviewRecord:
    """Representation of a single marketplace review stored on disk."""

    reviewer: str | None
    rating: int
    comment: str | None
    created_at: datetime


@dataclass(frozen=True)
class MarketplaceEntryRecord:
    """Representation of a published marketplace entry stored on disk."""

    identifier: str
    title: str
    description: str | None
    author: str | None
    tags: tuple[str, ...]
    created_at: datetime
    schema_version: int
    scenes: dict[str, Any]
    reviews: tuple[MarketplaceReviewRecord, ...]


@dataclass(frozen=True)
class ForumPostRecord:
    """Representation of an individual post stored within a forum thread."""

    identifier: str
    author: str | None
    body: str
    created_at: datetime


@dataclass(frozen=True)
class ForumThreadRecord:
    """Representation of a forum discussion thread stored on disk."""

    identifier: str
    title: str
    author: str | None
    created_at: datetime
    updated_at: datetime
    posts: tuple[ForumPostRecord, ...]


class MarketplaceStore:
    """Filesystem-backed storage for published marketplace entries."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.cwd() / "marketplace")

    def list(self) -> list[MarketplaceEntryRecord]:
        """Return all published entries ordered by recency."""

        if not self._root.exists():
            return []

        records: list[MarketplaceEntryRecord] = []
        for path in sorted(self._root.glob("*.json")):
            if not path.is_file():
                continue

            try:
                payload = _load_json(path)
            except (OSError, ValueError) as exc:
                raise ValueError(
                    f"Failed to load marketplace entry from '{path}'."
                ) from exc

            try:
                record = self._record_from_payload(payload, path)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            records.append(record)

        records.sort(key=lambda record: record.created_at, reverse=True)
        return records

    def load(self, identifier: str) -> MarketplaceEntryRecord:
        """Return the marketplace entry identified by ``identifier``."""

        normalised = _normalise_marketplace_identifier(identifier)
        path = self._path_for(normalised)
        if not path.exists():
            raise FileNotFoundError(f"Marketplace entry '{normalised}' does not exist.")

        try:
            payload = _load_json(path)
        except (OSError, ValueError) as exc:
            raise ValueError(
                f"Failed to load marketplace entry from '{path}'."
            ) from exc

        return self._record_from_payload(payload, path)

    def save(self, record: MarketplaceEntryRecord) -> None:
        """Persist ``record`` to disk, ensuring identifiers remain unique."""

        path = self._path_for(record.identifier)
        if path.exists():
            raise FileExistsError(
                f"Marketplace entry '{record.identifier}' already exists."
            )

        self._write_record(record, allow_overwrite=False)

    def update(self, record: MarketplaceEntryRecord) -> None:
        """Persist ``record`` to disk, replacing any existing entry."""

        path = self._path_for(record.identifier)
        if not path.exists():
            raise FileNotFoundError(
                f"Marketplace entry '{record.identifier}' does not exist."
            )

        self._write_record(record, allow_overwrite=True)

    def add_review(
        self, identifier: str, review: MarketplaceReviewRecord
    ) -> MarketplaceEntryRecord:
        """Append ``review`` to the entry identified by ``identifier``."""

        record = self.load(identifier)
        updated = MarketplaceEntryRecord(
            identifier=record.identifier,
            title=record.title,
            description=record.description,
            author=record.author,
            tags=record.tags,
            created_at=record.created_at,
            schema_version=record.schema_version,
            scenes=record.scenes,
            reviews=record.reviews + (review,),
        )

        self.update(updated)
        return updated

    def exists(self, identifier: str) -> bool:
        """Return whether an entry with ``identifier`` already exists."""

        normalised = _normalise_marketplace_identifier(identifier)
        return self._path_for(normalised).exists()

    def _path_for(self, identifier: str) -> Path:
        return self._root / f"{identifier}.json"

    def _write_record(
        self, record: MarketplaceEntryRecord, *, allow_overwrite: bool
    ) -> None:
        path = self._path_for(record.identifier)
        if not allow_overwrite and path.exists():
            raise FileExistsError(
                f"Marketplace entry '{record.identifier}' already exists."
            )

        serialisable_scenes = _ensure_serialisable_scene_mapping(record.scenes)
        payload = {
            "id": record.identifier,
            "title": record.title,
            "description": record.description,
            "author": record.author,
            "tags": list(record.tags),
            "created_at": record.created_at.isoformat(),
            "schema_version": record.schema_version,
            "scenes": serialisable_scenes,
            "reviews": [
                {
                    "reviewer": review.reviewer,
                    "rating": review.rating,
                    "comment": review.comment,
                    "created_at": review.created_at.isoformat(),
                }
                for review in record.reviews
            ],
        }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                "Failed to prepare marketplace storage directory."
            ) from exc

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError("Failed to persist marketplace entry.") from exc

    def _record_from_payload(
        self, payload: Mapping[str, Any], path: Path
    ) -> MarketplaceEntryRecord:
        if not isinstance(payload, Mapping):
            raise ValueError(f"Marketplace entry in '{path}' must be a mapping.")

        identifier = payload.get("id")
        title = payload.get("title")
        description = payload.get("description")
        author = payload.get("author")
        tags_raw = payload.get("tags")
        created_at_raw = payload.get("created_at")
        schema_version = payload.get("schema_version")
        scenes = payload.get("scenes")
        reviews_raw = payload.get("reviews")

        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"Marketplace entry in '{path}' is missing a valid 'id'.")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"Marketplace entry in '{path}' is missing a valid 'title'."
            )
        if not isinstance(created_at_raw, str):
            raise ValueError(
                f"Marketplace entry in '{path}' is missing a valid 'created_at'."
            )
        if not isinstance(schema_version, int):
            raise ValueError(
                f"Marketplace entry in '{path}' is missing a valid 'schema_version'."
            )
        if not isinstance(scenes, Mapping):
            raise ValueError(
                f"Marketplace entry in '{path}' must include a mapping of scenes."
            )

        normalised_description = _normalise_optional_text(description)
        normalised_author = _normalise_optional_text(author)
        tags: tuple[str, ...]
        if tags_raw is None:
            tags = ()
        elif isinstance(tags_raw, Iterable) and not isinstance(tags_raw, (str, bytes)):
            processed: list[str] = []
            seen: set[str] = set()
            for index, tag in enumerate(tags_raw):
                if not isinstance(tag, str):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid tag at "
                            f"index {index}."
                        )
                    )
                candidate = _normalise_optional_text(tag) or ""
                if not candidate:
                    continue
                slug = candidate.casefold()
                if slug in seen:
                    continue
                seen.add(slug)
                processed.append(slug)
            tags = tuple(processed)
        else:
            raise ValueError(
                f"Marketplace entry in '{path}' has an invalid 'tags' collection."
            )

        try:
            created_at = _ensure_timezone(datetime.fromisoformat(created_at_raw))
        except ValueError as exc:
            raise ValueError(
                f"Marketplace entry in '{path}' contains an invalid 'created_at'."
            ) from exc

        serialisable_scenes = _ensure_serialisable_scene_mapping(scenes)
        reviews: tuple[MarketplaceReviewRecord, ...]
        if reviews_raw is None:
            reviews = ()
        elif isinstance(reviews_raw, Iterable) and not isinstance(
            reviews_raw, (str, bytes)
        ):
            parsed_reviews: list[MarketplaceReviewRecord] = []
            for index, item in enumerate(reviews_raw):
                if not isinstance(item, Mapping):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid review "
                            f"payload at index {index}."
                        )
                    )

                reviewer_raw = item.get("reviewer")
                comment_raw = item.get("comment")
                rating = item.get("rating")
                created_at_raw = item.get("created_at")

                if rating is None or not isinstance(rating, int):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid "
                            f"review rating at index {index}."
                        )
                    )
                if rating < 1 or rating > 5:
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has a review rating "
                            f"outside the 1-5 range at index {index}."
                        )
                    )
                if not isinstance(created_at_raw, str):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid "
                            f"review timestamp at index {index}."
                        )
                    )

                try:
                    created_at = _ensure_timezone(
                        datetime.fromisoformat(created_at_raw)
                    )
                except ValueError as exc:
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has a review with an "
                            f"invalid timestamp at index {index}."
                        )
                    ) from exc

                reviewer = (
                    _normalise_optional_text(reviewer_raw)
                    if isinstance(reviewer_raw, str) or reviewer_raw is None
                    else None
                )
                if reviewer_raw is not None and not isinstance(reviewer_raw, str):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid "
                            f"reviewer value at index {index}."
                        )
                    )

                if comment_raw is not None and not isinstance(comment_raw, str):
                    raise ValueError(
                        (
                            f"Marketplace entry in '{path}' has an invalid "
                            f"review comment at index {index}."
                        )
                    )
                comment = _normalise_optional_text(comment_raw)

                parsed_reviews.append(
                    MarketplaceReviewRecord(
                        reviewer=reviewer,
                        rating=rating,
                        comment=comment,
                        created_at=created_at,
                    )
                )

            reviews = tuple(parsed_reviews)
        else:
            raise ValueError(
                f"Marketplace entry in '{path}' has an invalid 'reviews' collection."
            )

        return MarketplaceEntryRecord(
            identifier=_normalise_marketplace_identifier(identifier),
            title=title.strip(),
            description=normalised_description,
            author=normalised_author,
            tags=tags,
            created_at=created_at,
            schema_version=schema_version,
            scenes=serialisable_scenes,
            reviews=reviews,
        )


class ForumStore:
    """Filesystem-backed storage for community discussion threads."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.cwd() / "forums")

    def list(self) -> list[ForumThreadRecord]:
        """Return all forum threads ordered by most recent activity."""

        if not self._root.exists():
            return []

        records: list[ForumThreadRecord] = []
        for path in sorted(self._root.glob("*.json")):
            if not path.is_file():
                continue

            try:
                payload = _load_json(path)
            except (OSError, ValueError) as exc:
                raise ValueError(f"Failed to load forum thread from '{path}'.") from exc

            try:
                record = self._record_from_payload(payload, path)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            records.append(record)

        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records

    def load(self, identifier: str) -> ForumThreadRecord:
        """Return the thread identified by ``identifier``."""

        normalised = _normalise_forum_identifier(identifier)
        path = self._path_for(normalised)
        if not path.exists():
            raise FileNotFoundError(f"Forum thread '{normalised}' does not exist.")

        try:
            payload = _load_json(path)
        except (OSError, ValueError) as exc:
            raise ValueError(f"Failed to load forum thread from '{path}'.") from exc

        return self._record_from_payload(payload, path)

    def save(self, record: ForumThreadRecord) -> None:
        """Persist ``record`` ensuring the identifier remains unique."""

        path = self._path_for(record.identifier)
        if path.exists():
            raise FileExistsError(f"Forum thread '{record.identifier}' already exists.")

        self._write_record(record, allow_overwrite=False)

    def update(self, record: ForumThreadRecord) -> None:
        """Replace any existing record for the thread with ``record``."""

        path = self._path_for(record.identifier)
        if not path.exists():
            raise FileNotFoundError(
                f"Forum thread '{record.identifier}' does not exist."
            )

        self._write_record(record, allow_overwrite=True)

    def exists(self, identifier: str) -> bool:
        """Return whether a thread with ``identifier`` is already stored."""

        normalised = _normalise_forum_identifier(identifier)
        return self._path_for(normalised).exists()

    def _path_for(self, identifier: str) -> Path:
        return self._root / f"{identifier}.json"

    def _write_record(
        self, record: ForumThreadRecord, *, allow_overwrite: bool
    ) -> None:
        path = self._path_for(record.identifier)
        if not allow_overwrite and path.exists():
            raise FileExistsError(f"Forum thread '{record.identifier}' already exists.")

        payload = {
            "id": record.identifier,
            "title": record.title,
            "author": record.author,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "posts": [
                {
                    "id": post.identifier,
                    "author": post.author,
                    "body": post.body,
                    "created_at": post.created_at.isoformat(),
                }
                for post in record.posts
            ],
        }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError("Failed to prepare forum storage directory.") from exc

        try:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            raise RuntimeError("Failed to persist forum thread.") from exc

    def _record_from_payload(
        self, payload: Mapping[str, Any], path: Path
    ) -> ForumThreadRecord:
        if not isinstance(payload, Mapping):
            raise ValueError(f"Forum thread in '{path}' must be a mapping.")

        identifier_raw = payload.get("id")
        title_raw = payload.get("title")
        author_raw = payload.get("author")
        created_at_raw = payload.get("created_at")
        updated_at_raw = payload.get("updated_at")
        posts_raw = payload.get("posts")

        if not isinstance(identifier_raw, str) or not identifier_raw.strip():
            raise ValueError(f"Forum thread in '{path}' is missing a valid 'id'.")
        if not isinstance(title_raw, str) or not title_raw.strip():
            raise ValueError(f"Forum thread in '{path}' is missing a valid 'title'.")
        if author_raw is not None and not isinstance(author_raw, str):
            raise ValueError(f"Forum thread in '{path}' has an invalid 'author'.")
        if not isinstance(created_at_raw, str):
            raise ValueError(
                f"Forum thread in '{path}' is missing a valid 'created_at'."
            )
        if not isinstance(updated_at_raw, str):
            raise ValueError(
                f"Forum thread in '{path}' is missing a valid 'updated_at'."
            )
        if not isinstance(posts_raw, Sequence) or isinstance(
            posts_raw, (str, bytes, bytearray)
        ):
            raise ValueError(f"Forum thread in '{path}' must include a list of posts.")

        author = _normalise_optional_text(author_raw)

        try:
            created_at = _ensure_timezone(datetime.fromisoformat(created_at_raw))
        except ValueError as exc:
            raise ValueError(
                f"Forum thread in '{path}' contains an invalid 'created_at'."
            ) from exc

        try:
            updated_at = _ensure_timezone(datetime.fromisoformat(updated_at_raw))
        except ValueError as exc:
            raise ValueError(
                f"Forum thread in '{path}' contains an invalid 'updated_at'."
            ) from exc

        posts: list[ForumPostRecord] = []
        for index, entry in enumerate(posts_raw):
            if not isinstance(entry, Mapping):
                raise ValueError(
                    f"Forum thread in '{path}' has an invalid post at index {index}."
                )

            post_id_raw = entry.get("id")
            post_body_raw = entry.get("body")
            post_author_raw = entry.get("author")
            post_created_at_raw = entry.get("created_at")

            if not isinstance(post_id_raw, str) or not post_id_raw.strip():
                raise ValueError(
                    (
                        f"Forum thread in '{path}' has a post with an invalid "
                        f"'id' at index {index}."
                    )
                )
            if not isinstance(post_body_raw, str) or not post_body_raw.strip():
                raise ValueError(
                    (
                        f"Forum thread in '{path}' has a post with an invalid "
                        f"'body' at index {index}."
                    )
                )
            if post_author_raw is not None and not isinstance(post_author_raw, str):
                raise ValueError(
                    (
                        f"Forum thread in '{path}' has a post with an invalid "
                        f"'author' at index {index}."
                    )
                )
            if not isinstance(post_created_at_raw, str):
                raise ValueError(
                    (
                        f"Forum thread in '{path}' has a post with an invalid "
                        f"'created_at' at index {index}."
                    )
                )

            try:
                post_created_at = _ensure_timezone(
                    datetime.fromisoformat(post_created_at_raw)
                )
            except ValueError as exc:
                raise ValueError(
                    (
                        f"Forum thread in '{path}' has a post with an invalid "
                        f"'created_at' at index {index}."
                    )
                ) from exc

            post_author = _normalise_optional_text(post_author_raw)

            posts.append(
                ForumPostRecord(
                    identifier=post_id_raw.strip(),
                    author=post_author,
                    body=post_body_raw.strip(),
                    created_at=post_created_at,
                )
            )

        if not posts:
            raise ValueError(
                f"Forum thread in '{path}' must contain at least one post."
            )

        posts.sort(key=lambda record: record.created_at)
        normalised_identifier = _normalise_forum_identifier(identifier_raw)
        thread_updated_at = max(updated_at, posts[-1].created_at)

        return ForumThreadRecord(
            identifier=normalised_identifier,
            title=title_raw.strip(),
            author=author,
            created_at=created_at,
            updated_at=thread_updated_at,
            posts=tuple(posts),
        )


class ForumService:
    """Business logic supporting the discussion forum endpoints."""

    def __init__(self, store: ForumStore) -> None:
        self._store = store

    def list_threads(self, *, page: int, page_size: int) -> ForumThreadListResponse:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1.")
        if page_size < 1:
            raise ValueError("page_size must be greater than or equal to 1.")

        records = self._store.list()

        total_items = len(records)
        total_pages = _compute_total_pages(total_items, page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        visible = records[start_index:end_index]

        summaries = [_build_forum_thread_summary(record) for record in visible]
        return ForumThreadListResponse(
            data=summaries,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )

    def create_thread(self, payload: ForumThreadCreateRequest) -> ForumThreadRecord:
        identifier = (
            _normalise_forum_identifier(payload.identifier)
            if payload.identifier is not None
            else self._generate_identifier(payload.title)
        )

        now = datetime.now(timezone.utc)
        initial_post = ForumPostRecord(
            identifier=uuid.uuid4().hex,
            author=payload.author,
            body=payload.body,
            created_at=now,
        )

        record = ForumThreadRecord(
            identifier=identifier,
            title=payload.title,
            author=payload.author,
            created_at=now,
            updated_at=now,
            posts=(initial_post,),
        )

        try:
            self._store.save(record)
        except FileExistsError as exc:
            raise ForumThreadAlreadyExistsError(identifier) from exc

        return record

    def get_thread(self, identifier: str) -> ForumThreadRecord:
        try:
            return self._store.load(identifier)
        except FileNotFoundError as exc:
            normalised = _normalise_forum_identifier(identifier)
            raise KeyError(f"Forum thread '{normalised}' does not exist.") from exc

    def add_post(
        self, identifier: str, payload: ForumPostCreateRequest
    ) -> ForumPostRecord:
        normalised_identifier = _normalise_forum_identifier(identifier)
        try:
            record = self._store.load(normalised_identifier)
        except FileNotFoundError as exc:
            raise KeyError(
                f"Forum thread '{normalised_identifier}' does not exist."
            ) from exc

        now = datetime.now(timezone.utc)
        post = ForumPostRecord(
            identifier=uuid.uuid4().hex,
            author=payload.author,
            body=payload.body,
            created_at=now,
        )

        updated_record = ForumThreadRecord(
            identifier=record.identifier,
            title=record.title,
            author=record.author,
            created_at=record.created_at,
            updated_at=now,
            posts=record.posts + (post,),
        )

        try:
            self._store.update(updated_record)
        except FileNotFoundError as exc:
            raise KeyError(
                f"Forum thread '{normalised_identifier}' does not exist."
            ) from exc

        return post

    def _generate_identifier(self, title: str) -> str:
        base_slug = _slugify_forum_identifier(title)
        if not base_slug:
            base_slug = f"thread-{uuid.uuid4().hex[:8]}"

        candidate = base_slug
        suffix = 1
        while True:
            if not self._store.exists(candidate):
                return candidate
            suffix += 1
            candidate = f"{base_slug}-{suffix}"


class ProjectService:
    """Business logic supporting the project management endpoints."""

    def __init__(
        self,
        store: SceneProjectStore,
        *,
        user_service: "UserService | None" = None,
    ) -> None:
        self._store = store
        self._user_service = user_service
        self._collaboration_default_ttl = self._validate_collaboration_ttl(
            _DEFAULT_COLLABORATION_TTL_SECONDS
        )

    def list_projects(self) -> AdventureProjectListResponse:
        records = self._store.list()
        return AdventureProjectListResponse(
            data=[_build_project_resource(record) for record in records]
        )

    def get_project(self, identifier: str) -> AdventureProjectDetailResponse:
        record = self._store.load(identifier)
        resource, scenes = _build_project_detail(record)
        return AdventureProjectDetailResponse(data=resource, scenes=scenes)

    def export_project(self, identifier: str) -> ProjectExportArchive:
        """Return a ZIP archive capturing the full project directory."""

        return self._store.export_archive(identifier)

    def create_project(
        self,
        *,
        identifier: str,
        scenes: Mapping[str, Any],
        name: str | None = None,
        description: str | None = None,
        scene_filename: str | None = None,
    ) -> AdventureProjectDetailResponse:
        record = self._store.create(
            identifier=identifier,
            scenes=scenes,
            name=name,
            description=description,
            scene_filename=scene_filename,
        )
        resource, created_scenes = _build_project_detail(record)
        return AdventureProjectDetailResponse(data=resource, scenes=created_scenes)

    def list_project_assets(self, identifier: str) -> ProjectAssetListResponse:
        record = self._store.load(identifier)
        assets_root = record.scene_path.parent / "assets"
        resources = _build_project_asset_listing(assets_root)
        return ProjectAssetListResponse(
            project_id=record.identifier,
            root="assets",
            generated_at=datetime.now(timezone.utc),
            assets=resources,
        )

    def fetch_project_asset(
        self, identifier: str, asset_path: str
    ) -> ProjectAssetContent:
        """Return the binary payload for ``asset_path`` within the project's assets."""

        record = self._store.load(identifier)
        assets_root = record.scene_path.parent / "assets"

        if assets_root.exists() and not assets_root.is_dir():
            raise ValueError(
                f"Project assets directory '{assets_root}' must be a directory when present."
            )

        if not assets_root.exists():
            raise FileNotFoundError(
                f"Project '{record.identifier}' does not have an assets directory."
            )

        relative_path = _normalise_project_asset_path(asset_path)
        target_path = assets_root / relative_path

        if not target_path.exists():
            raise FileNotFoundError(
                f"Asset '{relative_path.as_posix()}' does not exist for project '{record.identifier}'."
            )

        if not target_path.is_file():
            raise ValueError(
                f"Asset '{relative_path.as_posix()}' is not a file and cannot be downloaded."
            )

        try:
            content = target_path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"Failed to read asset '{relative_path.as_posix()}' for project '{record.identifier}'."
            ) from exc

        content_type, _ = mimetypes.guess_type(target_path.name)
        return ProjectAssetContent(
            filename=target_path.name,
            content=content,
            content_type=content_type,
        )

    def store_project_asset(
        self,
        identifier: str,
        asset_path: str,
        content: bytes | bytearray,
        *,
        acting_user_id: str | None = None,
    ) -> ProjectAssetResource:
        """Persist ``content`` under ``asset_path`` within the project's assets."""

        if not isinstance(content, (bytes, bytearray)):
            raise ValueError("Project asset content must be provided as bytes.")

        record = self._store.load(identifier)
        self._require_project_permission(
            record,
            acting_user_id=acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="upload assets",
        )
        assets_root = record.scene_path.parent / "assets"

        if assets_root.exists() and not assets_root.is_dir():
            raise ValueError(
                f"Project assets directory '{assets_root}' must be a directory when present."
            )

        try:
            assets_root.mkdir(exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare assets directory for project '{record.identifier}'."
            ) from exc

        relative_path = _normalise_project_asset_path(asset_path)
        target_path = assets_root / relative_path

        if target_path.exists() and target_path.is_dir():
            raise ValueError(
                f"Asset '{relative_path.as_posix()}' is a directory and cannot be overwritten."
            )

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare directory for asset '{relative_path.as_posix()}' in project '{record.identifier}'."
            ) from exc

        try:
            with target_path.open("wb") as handle:
                handle.write(bytes(content))
        except OSError as exc:
            raise RuntimeError(
                f"Failed to write asset '{relative_path.as_posix()}' for project '{record.identifier}'."
            ) from exc

        try:
            size = target_path.stat().st_size
        except OSError as exc:
            raise RuntimeError(
                f"Failed to stat asset '{relative_path.as_posix()}' for project '{record.identifier}'."
            ) from exc

        content_type, _ = mimetypes.guess_type(target_path.name)
        return ProjectAssetResource(
            path=relative_path.as_posix(),
            name=target_path.name,
            type=ProjectAssetType.FILE,
            size=size,
            content_type=content_type,
            updated_at=_timestamp_for(target_path),
        )

    def delete_project_asset(
        self,
        identifier: str,
        asset_path: str,
        *,
        acting_user_id: str | None = None,
    ) -> None:
        """Remove ``asset_path`` from the project's assets directory."""

        record = self._store.load(identifier)
        self._require_project_permission(
            record,
            acting_user_id=acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="delete assets",
        )
        assets_root = record.scene_path.parent / "assets"

        if assets_root.exists() and not assets_root.is_dir():
            raise ValueError(
                f"Project assets directory '{assets_root}' must be a directory when present."
            )

        if not assets_root.exists():
            raise FileNotFoundError(
                f"Project '{record.identifier}' does not have an assets directory."
            )

        relative_path = _normalise_project_asset_path(asset_path)
        target_path = assets_root / relative_path

        if not target_path.exists():
            raise FileNotFoundError(
                f"Asset '{relative_path.as_posix()}' does not exist for project '{record.identifier}'."
            )

        try:
            if target_path.is_file():
                target_path.unlink()
            elif target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                raise ValueError(
                    f"Asset '{relative_path.as_posix()}' is not a file or directory."
                )
        except OSError as exc:
            raise RuntimeError(
                f"Failed to delete asset '{relative_path.as_posix()}' for project '{record.identifier}'."
            ) from exc

    def require_scene_dataset_permission(
        self,
        *,
        scene_path: Path,
        acting_user_id: str | None,
        allowed_roles: Sequence[CollaboratorRole],
        action: str,
    ) -> None:
        """Ensure the collaborator can perform ``action`` on the active dataset."""

        record = self._find_project_by_scene_path(scene_path)
        if record is None:
            return

        self._require_project_permission(
            record,
            acting_user_id=acting_user_id,
            allowed_roles=allowed_roles,
            action=action,
        )

    def list_project_collaborators(
        self, identifier: str
    ) -> ProjectCollaboratorListResponse:
        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        record = self._store.load(trimmed_identifier)
        collaborators = [
            ProjectCollaboratorResource(
                user_id=collaborator.user_id,
                role=collaborator.role,
                display_name=(
                    collaborator.display_name
                    if collaborator.display_name is not None
                    else self._resolve_collaborator_display_name(collaborator.user_id)
                ),
            )
            for collaborator in record.collaborators
        ]
        return ProjectCollaboratorListResponse(
            project_id=record.identifier,
            collaborators=collaborators,
        )

    def replace_project_collaborators(
        self,
        identifier: str,
        collaborators: Sequence[ProjectCollaboratorResource],
        *,
        acting_user_id: str | None = None,
    ) -> ProjectCollaboratorListResponse:
        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        record = self._store.load(trimmed_identifier)
        self._require_project_permission(
            record,
            acting_user_id=acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER,),
            action="manage collaborators",
        )

        collaborator_records = [
            ProjectCollaboratorRecord(
                user_id=collaborator.user_id,
                role=collaborator.role,
                display_name=collaborator.display_name,
            )
            for collaborator in collaborators
        ]

        if collaborator_records and not any(
            entry.role is CollaboratorRole.OWNER for entry in collaborator_records
        ):
            raise ValueError(
                f"Project '{trimmed_identifier}' must include at least one owner collaborator."
            )

        validated = _ensure_unique_collaborators(
            collaborator_records, trimmed_identifier
        )

        self._validate_collaborators_exist(validated, trimmed_identifier)

        updated_record = self._store.replace_collaborators(
            trimmed_identifier, validated
        )

        updated_collaborators = [
            ProjectCollaboratorResource(
                user_id=collaborator.user_id,
                role=collaborator.role,
                display_name=(
                    collaborator.display_name
                    if collaborator.display_name is not None
                    else self._resolve_collaborator_display_name(collaborator.user_id)
                ),
            )
            for collaborator in updated_record.collaborators
        ]

        return ProjectCollaboratorListResponse(
            project_id=updated_record.identifier,
            collaborators=updated_collaborators,
        )

    def list_collaboration_sessions(
        self, identifier: str
    ) -> ProjectCollaborationSessionListResponse:
        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        record = self._store.load(trimmed_identifier)
        now = datetime.now(timezone.utc)

        stored_sessions = list(self._store.load_collaboration_sessions(record))
        active_sessions: list[ProjectCollaborationSessionRecord] = []
        dirty = False

        for session in stored_sessions:
            role = self._find_collaborator_role(record, session.user_id)
            if session.expires_at <= now or role is None:
                dirty = True
                continue
            active_sessions.append(session)

        if dirty:
            active_sessions.sort(key=lambda entry: (entry.started_at, entry.session_id))
            self._store.save_collaboration_sessions(record, active_sessions)

        resources = self._build_collaboration_session_resources(record, active_sessions)
        return ProjectCollaborationSessionListResponse(
            project_id=record.identifier,
            sessions=resources,
        )

    def touch_collaboration_session(
        self,
        identifier: str,
        *,
        acting_user_id: str | None,
        session_id: str | None = None,
        scene_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> ProjectCollaborationSessionListResponse:
        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        if acting_user_id is None:
            raise ValueError(
                "Acting collaborator identifier must be provided for collaboration sessions."
            )

        trimmed_user_id = acting_user_id.strip()
        if not trimmed_user_id:
            raise ValueError(
                "Acting collaborator identifier must be provided for collaboration sessions."
            )

        record = self._store.load(trimmed_identifier)
        self._require_project_permission(
            record,
            acting_user_id=trimmed_user_id,
            allowed_roles=(
                CollaboratorRole.OWNER,
                CollaboratorRole.EDITOR,
                CollaboratorRole.VIEWER,
            ),
            action="join collaboration sessions",
        )

        trimmed_scene_id: str | None = None
        if scene_id is not None:
            if not isinstance(scene_id, str):
                raise ValueError(
                    "Scene identifier must be provided as a string when specified."
                )
            trimmed_scene = scene_id.strip()
            trimmed_scene_id = trimmed_scene or None

        trimmed_session_id: str | None = None
        if session_id is not None:
            if not isinstance(session_id, str):
                raise ValueError(
                    "Session identifier must be provided as a string when specified."
                )
            trimmed_session_id = session_id.strip()
            if not trimmed_session_id:
                raise ValueError(
                    "Session identifier must be a non-empty string when specified."
                )

        ttl = self._normalise_collaboration_ttl(ttl_seconds)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)

        stored_sessions = list(self._store.load_collaboration_sessions(record))
        active_sessions: list[ProjectCollaborationSessionRecord] = []
        for session in stored_sessions:
            role = self._find_collaborator_role(record, session.user_id)
            if session.expires_at <= now or role is None:
                continue
            active_sessions.append(session)

        session_map = {session.session_id: session for session in active_sessions}
        target_session_id = trimmed_session_id or uuid.uuid4().hex
        existing = session_map.get(target_session_id)

        if existing is not None and existing.user_id != trimmed_user_id:
            raise ProjectPermissionError(
                record.identifier,
                (
                    f"Project '{record.identifier}' collaboration session "
                    f"'{target_session_id}' cannot be updated by collaborator "
                    f"'{trimmed_user_id}'."
                ),
            )

        updated_session = ProjectCollaborationSessionRecord(
            session_id=target_session_id,
            user_id=trimmed_user_id,
            scene_id=trimmed_scene_id,
            started_at=existing.started_at if existing is not None else now,
            last_heartbeat=now,
            expires_at=expires_at,
        )

        refreshed_sessions = [
            session
            for session in active_sessions
            if session.session_id != target_session_id
        ]
        refreshed_sessions.append(updated_session)
        refreshed_sessions.sort(key=lambda entry: (entry.started_at, entry.session_id))

        persisted = self._store.save_collaboration_sessions(record, refreshed_sessions)
        resources = self._build_collaboration_session_resources(record, persisted)
        return ProjectCollaborationSessionListResponse(
            project_id=record.identifier,
            sessions=resources,
        )

    def end_collaboration_session(
        self,
        identifier: str,
        session_id: str,
        *,
        acting_user_id: str | None = None,
    ) -> ProjectCollaborationSessionListResponse:
        trimmed_identifier = identifier.strip()
        if not trimmed_identifier:
            raise ValueError("Project identifier must be provided.")

        if not isinstance(session_id, str):
            raise ValueError("Session identifier must be provided as a string.")

        trimmed_session_id = session_id.strip()
        if not trimmed_session_id:
            raise ValueError("Session identifier must be provided.")

        if acting_user_id is None:
            raise ValueError(
                "Acting collaborator identifier must be provided for collaboration sessions."
            )

        trimmed_user_id = acting_user_id.strip()
        if not trimmed_user_id:
            raise ValueError(
                "Acting collaborator identifier must be provided for collaboration sessions."
            )

        record = self._store.load(trimmed_identifier)
        self._require_project_permission(
            record,
            acting_user_id=trimmed_user_id,
            allowed_roles=(
                CollaboratorRole.OWNER,
                CollaboratorRole.EDITOR,
                CollaboratorRole.VIEWER,
            ),
            action="leave collaboration sessions",
        )

        now = datetime.now(timezone.utc)
        stored_sessions = list(self._store.load_collaboration_sessions(record))
        active_sessions: list[ProjectCollaborationSessionRecord] = []
        removed_session: ProjectCollaborationSessionRecord | None = None

        for session in stored_sessions:
            role = self._find_collaborator_role(record, session.user_id)
            if session.expires_at <= now or role is None:
                continue
            if session.session_id == trimmed_session_id:
                removed_session = session
                continue
            active_sessions.append(session)

        if removed_session is None:
            raise ValueError(
                (
                    f"Project '{record.identifier}' does not have an active collaboration "
                    f"session '{trimmed_session_id}'."
                )
            )

        actor_role = self._find_collaborator_role(record, trimmed_user_id)
        if actor_role is None:
            raise ValueError(
                f"Project '{record.identifier}' collaborator '{trimmed_user_id}' is invalid."
            )

        if removed_session.user_id != trimmed_user_id and actor_role not in (
            CollaboratorRole.OWNER,
            CollaboratorRole.EDITOR,
        ):
            raise ProjectPermissionError(
                record.identifier,
                (
                    f"Project '{record.identifier}' collaboration session "
                    f"'{trimmed_session_id}' can only be ended by the owning "
                    "collaborator or a project owner/editor."
                ),
            )

        active_sessions.sort(key=lambda entry: (entry.started_at, entry.session_id))
        persisted = self._store.save_collaboration_sessions(record, active_sessions)
        resources = self._build_collaboration_session_resources(record, persisted)
        return ProjectCollaborationSessionListResponse(
            project_id=record.identifier,
            sessions=resources,
        )

    def _require_project_permission(
        self,
        record: AdventureProjectRecord,
        *,
        acting_user_id: str | None,
        allowed_roles: Sequence[CollaboratorRole],
        action: str,
    ) -> None:
        if not record.collaborators:
            raise ProjectPermissionError(
                record.identifier,
                (
                    f"Project '{record.identifier}' cannot {action} because no collaborators "
                    "are configured to authorise the request."
                ),
            )

        if acting_user_id is None:
            raise ProjectPermissionError(
                record.identifier,
                (
                    f"Project '{record.identifier}' collaborator context is required to {action}."
                ),
            )

        trimmed_user_id = acting_user_id.strip()
        if not trimmed_user_id:
            raise ProjectPermissionError(
                record.identifier,
                (
                    f"Project '{record.identifier}' collaborator context is required to {action}."
                ),
            )

        for entry in record.collaborators:
            if entry.user_id == trimmed_user_id:
                if entry.role in allowed_roles:
                    return

                required = self._format_role_requirement(allowed_roles)
                raise ProjectPermissionError(
                    record.identifier,
                    (
                        f"Project '{record.identifier}' collaborator '{trimmed_user_id}' does not "
                        f"have permission to {action}. Required role: {required}."
                    ),
                )

        raise ProjectPermissionError(
            record.identifier,
            (
                f"Project '{record.identifier}' does not list '{trimmed_user_id}' as a collaborator "
                f"and cannot authorise the request to {action}."
            ),
        )

    def _find_project_by_scene_path(
        self, scene_path: Path
    ) -> AdventureProjectRecord | None:
        """Return the project whose dataset matches ``scene_path`` if available."""

        try:
            target = scene_path.expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            target = scene_path.expanduser()

        candidate_identifier = target.parent.name
        if candidate_identifier:
            try:
                candidate_record = self._store.load(candidate_identifier)
            except (FileNotFoundError, ValueError):
                candidate_record = None
            if candidate_record is not None and self._paths_equal(
                candidate_record.scene_path, target
            ):
                return candidate_record

        records: list[AdventureProjectRecord] = []
        try:
            records = self._store.list()
        except (FileNotFoundError, ValueError):
            root = getattr(self._store, "_root", None)
            if isinstance(root, Path) and root.exists():
                for entry in sorted(root.iterdir()):
                    if not entry.is_dir():
                        continue
                    try:
                        loaded = self._store.load(entry.name)
                    except (FileNotFoundError, ValueError):
                        continue
                    records.append(loaded)

        for record in records:
            if self._paths_equal(record.scene_path, target):
                return record

        return None

    @staticmethod
    def _paths_equal(candidate: Path, target: Path) -> bool:
        try:
            resolved_candidate = candidate.expanduser().resolve(strict=False)
        except (OSError, RuntimeError):
            resolved_candidate = candidate.expanduser()
        return resolved_candidate == target

    @staticmethod
    def _format_role_requirement(
        roles: Sequence[CollaboratorRole],
    ) -> str:
        labels = [role.value for role in roles]
        if not labels:
            return ""
        if len(labels) == 1:
            return labels[0]
        if len(labels) == 2:
            return " or ".join(labels)
        return ", ".join(labels[:-1]) + f", or {labels[-1]}"

    def _build_collaboration_session_resources(
        self,
        record: AdventureProjectRecord,
        sessions: Sequence[ProjectCollaborationSessionRecord],
    ) -> list[ProjectCollaborationSessionResource]:
        resources: list[ProjectCollaborationSessionResource] = []
        ordered = sorted(
            sessions, key=lambda entry: (entry.started_at, entry.session_id)
        )

        for session in ordered:
            role = self._find_collaborator_role(record, session.user_id)
            if role is None:
                continue
            resources.append(
                ProjectCollaborationSessionResource(
                    session_id=session.session_id,
                    user_id=session.user_id,
                    role=role,
                    display_name=self._resolve_collaborator_display_name(
                        session.user_id
                    ),
                    scene_id=session.scene_id,
                    started_at=session.started_at,
                    last_heartbeat=session.last_heartbeat,
                    expires_at=session.expires_at,
                )
            )

        return resources

    def _find_collaborator_role(
        self, record: AdventureProjectRecord, user_id: str
    ) -> CollaboratorRole | None:
        trimmed = user_id.strip()
        for entry in record.collaborators:
            if entry.user_id == trimmed:
                return entry.role
        return None

    def _normalise_collaboration_ttl(self, requested: int | None) -> int:
        if requested is None:
            return self._collaboration_default_ttl
        if not isinstance(requested, int):
            raise ValueError(
                "Collaboration timeout must be provided as an integer when specified."
            )
        return self._validate_collaboration_ttl(requested)

    @staticmethod
    def _validate_collaboration_ttl(value: int) -> int:
        if (
            value < _MIN_COLLABORATION_TTL_SECONDS
            or value > _MAX_COLLABORATION_TTL_SECONDS
        ):
            raise ValueError(
                (
                    "Collaboration timeout must be between "
                    f"{_MIN_COLLABORATION_TTL_SECONDS} and {_MAX_COLLABORATION_TTL_SECONDS} seconds."
                )
            )
        return value

    def _resolve_collaborator_display_name(self, user_id: str) -> str | None:
        service = self._user_service
        if service is None:
            return None

        try:
            profile = service.get_user(user_id)
        except FileNotFoundError:
            return None
        except ValueError:
            return None

        return profile.display_name

    def _validate_collaborators_exist(
        self,
        collaborators: Sequence[ProjectCollaboratorRecord],
        project_id: str,
    ) -> None:
        service = self._user_service
        if service is None or not collaborators:
            return

        missing: list[str] = []
        for entry in collaborators:
            try:
                service.get_user(entry.user_id)
            except FileNotFoundError:
                missing.append(entry.user_id)
            except ValueError as exc:
                raise ValueError(
                    f"Project '{project_id}' collaborator '{entry.user_id}' is invalid: {exc}"
                ) from exc

        if missing:
            ordered = sorted(dict.fromkeys(missing))
            formatted = ", ".join(ordered)
            raise ValueError(
                f"Project '{project_id}' references unknown collaborators: {formatted}."
            )


class UserService:
    """Business logic supporting the user management endpoints."""

    def __init__(self, store: UserAccountStore) -> None:
        self._store = store

    def list_users(self) -> UserProfileListResponse:
        records = self._store.list()
        resources = [_build_user_profile_resource(record) for record in records]
        return UserProfileListResponse(data=resources)

    def get_user(self, identifier: str) -> UserProfileResource:
        record = self._store.load(identifier)
        return _build_user_profile_resource(record)

    def create_user(
        self,
        *,
        identifier: str,
        display_name: str,
        email: str | None = None,
        bio: str | None = None,
    ) -> UserProfileResource:
        record = self._store.create(
            identifier=identifier,
            display_name=display_name,
            email=email,
            bio=bio,
        )
        return _build_user_profile_resource(record)

    def update_user(
        self,
        identifier: str,
        *,
        display_name: str | _UnsetType | None = _UNSET,
        email: str | _UnsetType | None = _UNSET,
        bio: str | _UnsetType | None = _UNSET,
    ) -> UserProfileResource:
        record = self._store.update(
            identifier,
            display_name=display_name,
            email=email,
            bio=bio,
        )
        return _build_user_profile_resource(record)


class ProjectTemplateService:
    """Service exposing project template listing and instantiation helpers."""

    def __init__(
        self,
        *,
        template_store: SceneProjectStore,
        project_service: ProjectService,
    ) -> None:
        self._template_store = template_store
        self._project_service = project_service

    def list_templates(self) -> AdventureProjectTemplateListResponse:
        records = self._template_store.list()
        resources = [
            AdventureProjectTemplateResource(
                **_build_project_resource(record).model_dump()
            )
            for record in records
        ]
        return AdventureProjectTemplateListResponse(data=resources)

    def instantiate_template(
        self,
        template_id: str,
        *,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> AdventureProjectDetailResponse:
        record = self._template_store.load(template_id)
        scenes, _, _ = _load_project_dataset(record)

        resolved_name = name if name is not None else record.name
        resolved_description = (
            description if description is not None else record.description
        )

        return self._project_service.create_project(
            identifier=project_id,
            scenes=scenes,
            name=resolved_name,
            description=resolved_description,
            scene_filename=record.scene_path.name,
        )


class MarketplaceEntryAlreadyExistsError(RuntimeError):
    """Raised when attempting to publish a duplicate marketplace entry."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Marketplace entry '{identifier}' already exists.")
        self.identifier = identifier


class ForumThreadAlreadyExistsError(RuntimeError):
    """Raised when attempting to create a forum thread with a duplicate id."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Forum thread '{identifier}' already exists.")
        self.identifier = identifier


class MarketplaceService:
    """Business logic supporting the marketplace entry endpoints."""

    def __init__(self, store: MarketplaceStore) -> None:
        self._store = store

    def publish_entry(
        self, payload: MarketplaceEntryPublishRequest
    ) -> MarketplaceEntryRecord:
        requested_identifier = payload.identifier
        if requested_identifier is not None:
            identifier = _normalise_marketplace_identifier(requested_identifier)
        else:
            identifier = self._generate_identifier(payload.title)

        scenes = _ensure_serialisable_scene_mapping(payload.scenes)
        record = MarketplaceEntryRecord(
            identifier=identifier,
            title=payload.title,
            description=payload.description,
            author=payload.author,
            tags=tuple(payload.tags),
            created_at=datetime.now(timezone.utc),
            schema_version=payload.schema_version,
            scenes=scenes,
            reviews=(),
        )

        try:
            self._store.save(record)
        except FileExistsError as exc:
            raise MarketplaceEntryAlreadyExistsError(identifier) from exc

        return record

    def list_entries(
        self,
        *,
        search: str | None,
        tag: str | None,
        page: int,
        page_size: int,
    ) -> MarketplaceEntryListResponse:
        if page < 1:
            raise ValueError("page must be greater than or equal to 1.")
        if page_size < 1:
            raise ValueError("page_size must be greater than or equal to 1.")

        records = self._store.list()

        search_term = _normalise_optional_text(search)
        search_query = search_term.casefold() if search_term else None
        resolved_tag = _normalise_marketplace_tag(tag) if tag is not None else None

        filtered: list[MarketplaceEntryRecord] = []
        for record in records:
            if search_query is not None:
                haystacks = [
                    record.identifier.casefold(),
                    record.title.casefold(),
                ]
                if record.description is not None:
                    haystacks.append(record.description.casefold())
                if not any(search_query in haystack for haystack in haystacks):
                    continue

            if resolved_tag is not None and resolved_tag not in record.tags:
                continue

            filtered.append(record)

        total_items = len(filtered)
        total_pages = _compute_total_pages(total_items, page_size)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        visible = filtered[start_index:end_index]

        summaries = [_build_marketplace_summary(record) for record in visible]
        return MarketplaceEntryListResponse(
            data=summaries,
            pagination=Pagination(
                page=page,
                page_size=page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )

    def get_entry(self, identifier: str) -> MarketplaceEntryRecord:
        try:
            return self._store.load(identifier)
        except FileNotFoundError as exc:
            normalised = _normalise_marketplace_identifier(identifier)
            raise KeyError(f"Marketplace entry '{normalised}' does not exist.") from exc

    def add_review(
        self, identifier: str, payload: MarketplaceReviewCreateRequest
    ) -> tuple[MarketplaceEntryRecord, MarketplaceReviewRecord]:
        try:
            normalised_identifier = _normalise_marketplace_identifier(identifier)
            review = MarketplaceReviewRecord(
                reviewer=_normalise_optional_text(payload.reviewer),
                rating=payload.rating,
                comment=_normalise_optional_text(payload.comment),
                created_at=datetime.now(timezone.utc),
            )
            updated = self._store.add_review(normalised_identifier, review)
        except FileNotFoundError as exc:
            raise KeyError(
                f"Marketplace entry '{normalised_identifier}' does not exist."
            ) from exc

        return updated, review

    def _generate_identifier(self, title: str) -> str:
        base_slug = _slugify_marketplace_identifier(title)
        if not base_slug:
            base_slug = f"entry-{uuid.uuid4().hex[:8]}"

        candidate = base_slug
        suffix = 2
        while self._store.exists(candidate):
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate


def _build_branch_resource(record: SceneBranchRecord) -> SceneBranchResource:
    return SceneBranchResource(
        id=record.identifier,
        name=record.name,
        created_at=record.created_at,
        base=record.plan.base,
        target=record.plan.target,
        expected_base_version_id=record.plan.expected_base_version_id,
        base_version_matches=record.plan.base_version_matches,
        summary=record.plan.summary,
        scene_count=len(record.scenes),
    )


def _build_branch_detail(record: SceneBranchRecord) -> SceneBranchDetailResponse:
    return SceneBranchDetailResponse(
        id=record.identifier,
        name=record.name,
        created_at=record.created_at,
        base=record.plan.base,
        target=record.plan.target,
        expected_base_version_id=record.plan.expected_base_version_id,
        base_version_matches=record.plan.base_version_matches,
        summary=record.plan.summary,
        scene_count=len(record.scenes),
        entries=record.plan.entries,
        plans=record.plan.plans,
        scenes=record.scenes,
    )


def _build_user_profile_resource(record: UserAccountRecord) -> UserProfileResource:
    return UserProfileResource(
        id=record.identifier,
        display_name=record.display_name,
        email=record.email,
        bio=record.bio,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _build_project_asset_listing(root: Path) -> list[ProjectAssetResource]:
    if not root.exists():
        return []

    if not root.is_dir():
        raise ValueError(
            f"Project assets directory '{root}' must be a directory when present."
        )

    resources: list[ProjectAssetResource] = []

    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames.sort()
        filenames.sort()

        for dirname in dirnames:
            directory_path = current_path / dirname
            relative_path = directory_path.relative_to(root).as_posix()
            resources.append(
                ProjectAssetResource(
                    path=relative_path,
                    name=dirname,
                    type=ProjectAssetType.DIRECTORY,
                    updated_at=_timestamp_for(directory_path),
                )
            )

        for filename in filenames:
            file_path = current_path / filename
            relative_path = file_path.relative_to(root).as_posix()
            try:
                size = file_path.stat().st_size
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to read project asset '{file_path}'."
                ) from exc

            content_type, _ = mimetypes.guess_type(file_path.name)
            resources.append(
                ProjectAssetResource(
                    path=relative_path,
                    name=filename,
                    type=ProjectAssetType.FILE,
                    size=size,
                    content_type=content_type,
                    updated_at=_timestamp_for(file_path),
                )
            )

    return resources


def _normalise_project_asset_path(path: str) -> Path:
    """Return a sanitised relative path for locating a project asset."""

    if not isinstance(path, str):
        raise ValueError("Project asset path must be provided as a string.")

    trimmed = path.strip()
    if not trimmed:
        raise ValueError("Project asset path must be a non-empty string.")

    relative = Path(trimmed)
    if relative.is_absolute():
        raise ValueError("Project asset path must be relative to the assets directory.")

    parts: list[str] = []
    for segment in relative.parts:
        if segment in ("", "."):
            continue
        if segment == "..":
            raise ValueError(
                "Project asset path must not traverse outside the assets directory."
            )
        parts.append(segment)

    if not parts:
        raise ValueError(
            "Project asset path must reference a file within the assets directory."
        )

    return Path(*parts)


def _build_project_resource(record: AdventureProjectRecord) -> AdventureProjectResource:
    scenes, checksum, version_id = _load_project_dataset(record)
    return AdventureProjectResource(
        id=record.identifier,
        name=record.name,
        description=record.description,
        scene_count=len(scenes),
        collaborator_count=len(record.collaborators),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version_id=version_id,
        checksum=checksum,
    )


def _build_project_detail(
    record: AdventureProjectRecord,
) -> tuple[AdventureProjectResource, dict[str, Any]]:
    scenes, checksum, version_id = _load_project_dataset(record)
    resource = AdventureProjectResource(
        id=record.identifier,
        name=record.name,
        description=record.description,
        scene_count=len(scenes),
        collaborator_count=len(record.collaborators),
        created_at=record.created_at,
        updated_at=record.updated_at,
        version_id=version_id,
        checksum=checksum,
    )
    return resource, scenes


def _build_marketplace_summary(
    record: MarketplaceEntryRecord,
) -> MarketplaceEntrySummary:
    return MarketplaceEntrySummary(
        id=record.identifier,
        title=record.title,
        description=record.description,
        author=record.author,
        tags=list(record.tags),
        created_at=record.created_at,
        scene_count=len(record.scenes),
        average_rating=_compute_average_rating(record.reviews),
        review_count=len(record.reviews),
    )


def _build_marketplace_response(
    record: MarketplaceEntryRecord,
) -> MarketplaceEntryResponse:
    summary = _build_marketplace_summary(record)
    payload = summary.model_dump()
    payload.update(
        {
            "schema_version": record.schema_version,
            "scenes": record.scenes,
            "reviews": [
                _build_marketplace_review(review)
                for review in _sort_reviews_newest_first(record.reviews)
            ],
        }
    )
    return MarketplaceEntryResponse(**payload)


def _build_marketplace_review(
    record: MarketplaceReviewRecord,
) -> MarketplaceReview:
    return MarketplaceReview(
        reviewer=record.reviewer,
        rating=record.rating,
        comment=record.comment,
        created_at=record.created_at,
    )


def _build_forum_post(record: ForumPostRecord) -> ForumPostResource:
    return ForumPostResource(
        id=record.identifier,
        author=record.author,
        body=record.body,
        created_at=record.created_at,
    )


def _build_forum_thread_summary(record: ForumThreadRecord) -> ForumThreadSummary:
    return ForumThreadSummary(
        id=record.identifier,
        title=record.title,
        author=record.author,
        created_at=record.created_at,
        updated_at=record.updated_at,
        post_count=len(record.posts),
    )


def _build_forum_thread_detail(record: ForumThreadRecord) -> ForumThreadDetail:
    ordered_posts = sorted(record.posts, key=lambda post: post.created_at)
    resources = [_build_forum_post(post) for post in ordered_posts]
    return ForumThreadDetail(
        id=record.identifier,
        title=record.title,
        author=record.author,
        created_at=record.created_at,
        updated_at=record.updated_at,
        post_count=len(resources),
        posts=resources,
    )


def _compute_average_rating(
    reviews: Sequence[MarketplaceReviewRecord],
) -> float | None:
    if not reviews:
        return None

    total = sum(review.rating for review in reviews)
    average = total / len(reviews)
    return round(average, 2)


def _sort_reviews_newest_first(
    reviews: Sequence[MarketplaceReviewRecord],
) -> list[MarketplaceReviewRecord]:
    return sorted(reviews, key=lambda review: review.created_at, reverse=True)


def _load_project_dataset(
    record: AdventureProjectRecord,
) -> tuple[dict[str, Any], str, str]:
    try:
        payload = _load_json(record.scene_path)
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Failed to load project scenes from '{record.scene_path}'."
        ) from exc

    if not isinstance(payload, Mapping):
        raise ValueError(f"Project scenes in '{record.scene_path}' must be a mapping.")

    # Ensure the dataset can be parsed by the scripted story engine helpers.
    load_scenes_from_mapping(payload)

    try:
        serialisable_any = json.loads(json.dumps(payload, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Project scenes in '{record.scene_path}' could not be serialised to JSON."
        ) from exc

    if not isinstance(serialisable_any, dict):
        raise ValueError(f"Project scenes in '{record.scene_path}' must be a mapping.")

    serialisable = cast(dict[str, Any], serialisable_any)
    checksum = _compute_scene_checksum(serialisable)
    version_id = _format_version_id(record.updated_at, checksum)
    return serialisable, checksum, version_id


_USER_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._@-]*$")
_MARKETPLACE_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_MARKETPLACE_SLUG_SANITISE_RE = re.compile(r"[^a-z0-9]+")


def _normalise_user_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise ValueError("User identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("User identifier must be a non-empty string.")

    if not _USER_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "User identifier must only contain lowercase letters, numbers, periods, underscores, hyphens, and '@' symbols."
        )

    return slug


def _validate_display_name(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Display name must be provided as a string.")

    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Display name must be a non-empty string.")

    return trimmed


def _normalise_optional_email(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Email address must be provided as a string.")

    trimmed = value.strip()
    if not trimmed:
        return None

    if "@" not in trimmed:
        raise ValueError("Email address must contain an '@' symbol.")

    return trimmed


def _normalise_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Profile text must be provided as a string.")

    trimmed = value.strip()
    return trimmed or None


_FORUM_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FORUM_SLUG_SANITISE_RE = re.compile(r"[^a-z0-9]+")


def _normalise_forum_identifier(identifier: str | None) -> str:
    if not isinstance(identifier, str):
        raise ValueError("Forum thread identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("Forum thread identifier must be a non-empty string.")

    if not _FORUM_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "Forum thread identifier must contain only lowercase letters, numbers, and hyphens."
        )

    return slug


def _slugify_forum_identifier(value: str) -> str:
    if not isinstance(value, str):
        return ""

    trimmed = value.strip().casefold()
    if not trimmed:
        return ""

    slug = _FORUM_SLUG_SANITISE_RE.sub("-", trimmed)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _normalise_marketplace_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise ValueError("Marketplace identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("Marketplace identifier must be a non-empty string.")

    if not _MARKETPLACE_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "Marketplace identifier must only contain lowercase letters, numbers, and hyphens."
        )

    return slug


def _normalise_marketplace_tag(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Marketplace tag must be provided as a string.")

    trimmed = value.strip()
    if not trimmed:
        return None

    return trimmed.casefold()


_PROJECT_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def _normalise_project_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise ValueError("Project identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("Project identifier must be a non-empty string.")

    if not _PROJECT_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "Project identifier must only contain lowercase letters, numbers, hyphens, and underscores."
        )

    return slug


def _validate_scene_filename(filename: str | None) -> str:
    if filename is None:
        raise ValueError("Scene filename must be provided.")

    candidate = filename.strip()
    if not candidate:
        raise ValueError("Scene filename must be a non-empty string.")

    if Path(candidate).name != candidate:
        raise ValueError("Scene filename must not include directory components.")

    return candidate


def _ensure_serialisable_scene_mapping(scenes: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(scenes, Mapping):
        raise ValueError("Project scenes must be provided as a mapping.")

    load_scenes_from_mapping(scenes)

    try:
        serialisable_any = json.loads(json.dumps(scenes, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise ValueError("Project scenes could not be serialised to JSON.") from exc

    if not isinstance(serialisable_any, dict):
        raise ValueError("Project scenes must be serialisable as a JSON object.")

    return cast(dict[str, Any], serialisable_any)


def _slugify_marketplace_identifier(value: str) -> str:
    if not isinstance(value, str):
        return ""

    trimmed = value.strip().casefold()
    if not trimmed:
        return ""

    slug = _MARKETPLACE_SLUG_SANITISE_RE.sub("-", trimmed)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def _parse_collaborators(
    payload: Any, *, project_id: str
) -> tuple[ProjectCollaboratorRecord, ...]:
    if payload is None:
        return ()

    if not isinstance(payload, Sequence) or isinstance(
        payload, (str, bytes, bytearray)
    ):
        raise ValueError(
            f"Project '{project_id}' metadata has an invalid 'collaborators' field."
        )

    collaborators: list[ProjectCollaboratorRecord] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"Project '{project_id}' metadata collaborator at index {index} must be a mapping."
            )

        user_id_raw = entry.get("user_id")
        if not isinstance(user_id_raw, str):
            raise ValueError(
                f"Project '{project_id}' metadata collaborator at index {index} has an invalid 'user_id'."
            )

        user_id = user_id_raw.strip()
        if not user_id:
            raise ValueError(
                f"Project '{project_id}' metadata collaborator at index {index} has an empty 'user_id'."
            )

        role_raw = entry.get("role")
        if not isinstance(role_raw, str):
            raise ValueError(
                f"Project '{project_id}' metadata collaborator '{user_id}' is missing a role."
            )

        try:
            role = CollaboratorRole(role_raw)
        except ValueError as exc:
            raise ValueError(
                f"Project '{project_id}' metadata collaborator '{user_id}' has an unknown role '{role_raw}'."
            ) from exc

        display_name_raw = entry.get("display_name")
        if display_name_raw is None:
            display_name: str | None = None
        elif isinstance(display_name_raw, str):
            display_name = display_name_raw.strip() or None
        else:
            raise ValueError(
                f"Project '{project_id}' metadata collaborator '{user_id}' has an invalid display name."
            )

        collaborators.append(
            ProjectCollaboratorRecord(
                user_id=user_id,
                role=role,
                display_name=display_name,
            )
        )

    return _ensure_unique_collaborators(collaborators, project_id)


def _ensure_unique_collaborators(
    collaborators: Sequence[ProjectCollaboratorRecord],
    project_id: str,
) -> tuple[ProjectCollaboratorRecord, ...]:
    if not collaborators:
        return ()

    seen: set[str] = set()
    normalised: list[ProjectCollaboratorRecord] = []

    for entry in collaborators:
        user_id = entry.user_id.strip()
        if not user_id:
            raise ValueError(
                f"Project '{project_id}' collaborators must include non-empty user IDs."
            )

        if user_id in seen:
            raise ValueError(
                f"Project '{project_id}' collaborator '{user_id}' is defined multiple times."
            )

        seen.add(user_id)

        display_name = entry.display_name
        if display_name is not None:
            display_name = display_name.strip()
            if not display_name:
                display_name = None

        normalised.append(
            ProjectCollaboratorRecord(
                user_id=user_id,
                role=entry.role,
                display_name=display_name,
            )
        )

    return tuple(normalised)


def _serialise_collaborators(
    collaborators: Sequence[ProjectCollaboratorRecord],
) -> list[dict[str, Any]]:
    serialised: list[dict[str, Any]] = []
    for collaborator in collaborators:
        entry: dict[str, Any] = {
            "user_id": collaborator.user_id,
            "role": collaborator.role.value,
        }
        if collaborator.display_name is not None:
            entry["display_name"] = collaborator.display_name
        serialised.append(entry)
    return serialised


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify_branch_name(name: str) -> str:
    """Return a filesystem-friendly identifier derived from ``name``."""

    slug = _SLUG_PATTERN.sub("-", name.strip().casefold()).strip("-")
    return slug


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
class SceneGraphNodeData:
    """Internal representation of a graph node prior to serialisation."""

    id: str
    description: str
    choice_count: int
    transition_count: int
    has_terminal_transition: bool
    validation_status: ValidationStatus


@dataclass(frozen=True)
class SceneGraphEdgeData:
    """Internal representation of a graph edge prior to serialisation."""

    id: str
    source: str
    command: str
    target: str | None
    narration: str
    is_terminal: bool
    item: str | None
    requires: tuple[str, ...]
    consumes: tuple[str, ...]
    records: tuple[str, ...]
    failure_narration: str | None
    override_count: int


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
        path: Path | None = None,
    ) -> None:
        self._package = package
        self._resource_name = resource_name
        self._path = path

    @property
    def path(self) -> Path | None:
        """Return the filesystem path backing the repository when editable."""

        return self._path

    def load(self) -> tuple[Mapping[str, Any], datetime]:
        """Load scene definitions along with their last modified timestamp."""

        if self._path is not None:
            try:
                payload = _load_json(self._path)
                updated_at = _timestamp_for(self._path)
            except FileNotFoundError as exc:
                raise RuntimeError("Configured scene data file is missing.") from exc
            except OSError as exc:
                raise RuntimeError(
                    "Failed to read configured scene data file."
                ) from exc
        else:
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

    def save(self, scenes: Mapping[str, Any]) -> datetime:
        """Persist ``scenes`` to disk and return the resulting timestamp."""

        if self._path is None:
            raise RuntimeError(
                "Scene repository is read-only; configure TEXTADVENTURE_SCENE_PATH to enable editing."
            )

        try:
            serialisable = json.loads(json.dumps(scenes, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(serialisable, dict):
            raise ValueError("Scene data must be a JSON object.")

        destination = self._path
        destination.parent.mkdir(parents=True, exist_ok=True)

        temporary = (
            destination.with_suffix(destination.suffix + ".tmp")
            if destination.suffix
            else destination.with_suffix(".tmp")
        )

        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(serialisable, handle, ensure_ascii=False, indent=2)
            temporary.replace(destination)
        except OSError as exc:
            raise RuntimeError("Failed to persist scene data.") from exc

        return _timestamp_for(destination)


class SceneVersionConflictError(RuntimeError):
    """Raised when a dataset version check fails during a mutation."""

    def __init__(self, current_version_id: str) -> None:
        super().__init__(
            "Scene dataset has changed since the provided version identifier."
        )
        self.current_version_id = current_version_id


@dataclass(frozen=True)
class SceneReference:
    """Location where a scene is referenced by another definition."""

    scene_id: str
    command: str


class SceneAlreadyExistsError(RuntimeError):
    """Raised when attempting to create a scene that already exists."""

    def __init__(self, scene_id: str) -> None:
        super().__init__(f"Scene '{scene_id}' already exists.")
        self.scene_id = scene_id


class SceneDependencyError(RuntimeError):
    """Raised when deleting a scene that is still referenced elsewhere."""

    def __init__(self, scene_id: str, references: Sequence[SceneReference]) -> None:
        self.scene_id = scene_id
        self.references = tuple(references)
        if references:
            summary = ", ".join(
                f"{ref.scene_id} (command '{ref.command}')" for ref in references
            )
            message = (
                f"Scene '{scene_id}' cannot be deleted because it is referenced by: "
                f"{summary}."
            )
        else:
            message = f"Scene '{scene_id}' cannot be deleted because it is referenced by other scenes."
        super().__init__(message)


class SceneService:
    """Business logic supporting the API endpoints."""

    def __init__(
        self,
        repository: SceneRepository | None = None,
        branch_store: SceneBranchStore | None = None,
        *,
        automatic_backup_dir: Path | None = None,
        automatic_backup_retention: int | None = None,
        automatic_backup_export_format: ExportFormat = ExportFormat.PRETTY,
        automatic_backup_uploaders: Sequence[BackupUploader] | None = None,
    ) -> None:
        self._repository = repository or SceneRepository()
        self._branch_store = branch_store or SceneBranchStore()
        if automatic_backup_retention is not None and automatic_backup_retention < 1:
            raise ValueError("automatic_backup_retention must be greater than zero.")
        self._automatic_backup_dir = automatic_backup_dir
        self._automatic_backup_retention = automatic_backup_retention
        self._automatic_backup_export_format = automatic_backup_export_format
        self._automatic_backup_uploaders: tuple[BackupUploader, ...] = tuple(
            automatic_backup_uploaders or ()
        )

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

    def get_scene_graph(
        self,
        *,
        start_scene: str | None = None,
    ) -> SceneGraphResponse:
        """Return a connectivity graph describing scene transitions."""

        definitions, dataset_timestamp = self._repository.load()
        scenes = load_scenes_from_mapping(definitions)

        if not scenes:
            raise ValueError("No scenes are defined in the current dataset.")

        resolved_start = start_scene or "starting-area"
        if resolved_start not in scenes:
            if start_scene is None:
                resolved_start = next(iter(sorted(scenes.keys())))
            else:
                raise ValueError(f"Start scene '{start_scene}' is not defined.")

        validation_map = _compute_validation_statuses(cast(Mapping[str, Any], scenes))

        node_entries: list[SceneGraphNodeData] = []
        edge_entries: list[SceneGraphEdgeData] = []

        for scene_id in sorted(scenes):
            scene = scenes[scene_id]
            transitions = scene.transitions

            node_entries.append(
                SceneGraphNodeData(
                    id=scene_id,
                    description=scene.description,
                    choice_count=len(scene.choices),
                    transition_count=len(transitions),
                    has_terminal_transition=_has_terminal_transition(
                        transitions.values()
                    ),
                    validation_status=validation_map.get(scene_id, "valid"),
                )
            )

            for command in sorted(transitions):
                transition = transitions[command]
                edge_entries.append(
                    SceneGraphEdgeData(
                        id=f"{scene_id}:{command}",
                        source=scene_id,
                        command=command,
                        target=transition.target,
                        narration=transition.narration,
                        is_terminal=transition.target is None,
                        item=transition.item,
                        requires=tuple(transition.requires),
                        consumes=tuple(transition.consumes),
                        records=tuple(transition.records),
                        failure_narration=transition.failure_narration,
                        override_count=len(transition.narration_overrides),
                    )
                )

        nodes = [SceneGraphNodeResource(**asdict(entry)) for entry in node_entries]
        edges = [SceneGraphEdgeResource(**asdict(entry)) for entry in edge_entries]

        return SceneGraphResponse(
            generated_at=dataset_timestamp,
            start_scene=resolved_start,
            nodes=nodes,
            edges=edges,
        )

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

    def create_scene(
        self,
        *,
        scene_id: str,
        scene: Mapping[str, Any],
        schema_version: int | None = None,
        expected_version_id: str | None = None,
    ) -> SceneMutationResponse:
        """Persist a new scene definition identified by ``scene_id``."""

        if not scene_id or not scene_id.strip():
            raise ValueError("Scene identifier must be a non-empty string.")

        normalised_id = scene_id.strip()

        existing_definitions, dataset_timestamp = self._repository.load()

        try:
            current_serialisable = json.loads(
                json.dumps(existing_definitions, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(current_serialisable, dict):
            raise RuntimeError("Scene data must be a JSON object.")

        current_checksum = _compute_scene_checksum(current_serialisable)
        current_version_id = _format_version_id(dataset_timestamp, current_checksum)

        if (
            expected_version_id is not None
            and expected_version_id != current_version_id
        ):
            raise SceneVersionConflictError(current_version_id)

        if normalised_id in current_serialisable:
            raise SceneAlreadyExistsError(normalised_id)

        if self._automatic_backup_dir is not None or self._automatic_backup_uploaders:
            self._maybe_create_automatic_backup(
                dataset=current_serialisable,
                generated_at=_ensure_timezone(dataset_timestamp),
                version_id=current_version_id,
                checksum=current_checksum,
            )

        try:
            migrated = _migrate_scene_dataset(
                {normalised_id: scene}, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        migrated_scene = migrated[normalised_id]

        updated_definitions = dict(existing_definitions)
        updated_definitions[normalised_id] = migrated_scene

        serialisable_dataset = _ensure_serialisable_scene_mapping(updated_definitions)

        updated_timestamp = self._repository.save(serialisable_dataset)

        checksum = _compute_scene_checksum(serialisable_dataset)
        version_id = _format_version_id(updated_timestamp, checksum)

        scenes = load_scenes_from_mapping(serialisable_dataset)
        scene_object = scenes[normalised_id]

        validation_issues = _collect_validation_issues(
            normalised_id, cast(Mapping[str, Any], scenes)
        )
        validation = (
            SceneValidation(issues=validation_issues) if validation_issues else None
        )

        resource = _build_scene_resource(normalised_id, scene_object, updated_timestamp)

        return SceneMutationResponse(
            data=resource,
            validation=validation,
            version=SceneVersionInfo(
                generated_at=updated_timestamp,
                version_id=version_id,
                checksum=checksum,
            ),
        )

    def update_scene(
        self,
        *,
        scene_id: str,
        scene: Mapping[str, Any],
        schema_version: int | None = None,
        expected_version_id: str | None = None,
    ) -> SceneMutationResponse:
        """Persist an updated definition for ``scene_id``."""

        if not scene_id or not scene_id.strip():
            raise ValueError("Scene identifier must be a non-empty string.")

        normalised_id = scene_id.strip()

        existing_definitions, dataset_timestamp = self._repository.load()

        if normalised_id not in existing_definitions:
            raise KeyError(f"Scene '{normalised_id}' does not exist.")

        try:
            current_serialisable = json.loads(
                json.dumps(existing_definitions, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(current_serialisable, dict):
            raise RuntimeError("Scene data must be a JSON object.")

        current_checksum = _compute_scene_checksum(current_serialisable)
        current_version_id = _format_version_id(dataset_timestamp, current_checksum)

        if (
            expected_version_id is not None
            and expected_version_id != current_version_id
        ):
            raise SceneVersionConflictError(current_version_id)

        if self._automatic_backup_dir is not None or self._automatic_backup_uploaders:
            self._maybe_create_automatic_backup(
                dataset=current_serialisable,
                generated_at=_ensure_timezone(dataset_timestamp),
                version_id=current_version_id,
                checksum=current_checksum,
            )

        try:
            migrated = _migrate_scene_dataset(
                {normalised_id: scene}, schema_version=schema_version
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        migrated_scene = migrated[normalised_id]

        updated_definitions = dict(existing_definitions)
        updated_definitions[normalised_id] = migrated_scene

        serialisable_dataset = _ensure_serialisable_scene_mapping(updated_definitions)

        updated_timestamp = self._repository.save(serialisable_dataset)

        checksum = _compute_scene_checksum(serialisable_dataset)
        version_id = _format_version_id(updated_timestamp, checksum)

        scenes = load_scenes_from_mapping(serialisable_dataset)
        scene_object = scenes[normalised_id]

        validation_issues = _collect_validation_issues(
            normalised_id, cast(Mapping[str, Any], scenes)
        )
        validation = (
            SceneValidation(issues=validation_issues) if validation_issues else None
        )

        resource = _build_scene_resource(normalised_id, scene_object, updated_timestamp)

        return SceneMutationResponse(
            data=resource,
            validation=validation,
            version=SceneVersionInfo(
                generated_at=updated_timestamp,
                version_id=version_id,
                checksum=checksum,
            ),
        )

    def delete_scene(
        self,
        *,
        scene_id: str,
        expected_version_id: str | None = None,
    ) -> SceneDeleteResponse:
        """Remove the scene identified by ``scene_id`` from the dataset."""

        if not scene_id or not scene_id.strip():
            raise ValueError("Scene identifier must be a non-empty string.")

        normalised_id = scene_id.strip()

        existing_definitions, dataset_timestamp = self._repository.load()

        if normalised_id not in existing_definitions:
            raise KeyError(f"Scene '{normalised_id}' does not exist.")

        try:
            current_serialisable = json.loads(
                json.dumps(existing_definitions, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(current_serialisable, dict):
            raise RuntimeError("Scene data must be a JSON object.")

        current_checksum = _compute_scene_checksum(current_serialisable)
        current_version_id = _format_version_id(dataset_timestamp, current_checksum)

        if (
            expected_version_id is not None
            and expected_version_id != current_version_id
        ):
            raise SceneVersionConflictError(current_version_id)

        scenes = load_scenes_from_mapping(existing_definitions)
        references = _find_scene_references(
            normalised_id, cast(Mapping[str, Any], scenes)
        )
        if references:
            raise SceneDependencyError(normalised_id, references)

        if self._automatic_backup_dir is not None or self._automatic_backup_uploaders:
            self._maybe_create_automatic_backup(
                dataset=current_serialisable,
                generated_at=_ensure_timezone(dataset_timestamp),
                version_id=current_version_id,
                checksum=current_checksum,
            )

        updated_definitions = dict(existing_definitions)
        updated_definitions.pop(normalised_id)

        serialisable_dataset = _ensure_serialisable_scene_mapping(updated_definitions)

        updated_timestamp = self._repository.save(serialisable_dataset)

        checksum = _compute_scene_checksum(serialisable_dataset)
        version_id = _format_version_id(updated_timestamp, checksum)

        return SceneDeleteResponse(
            scene_id=normalised_id,
            version=SceneVersionInfo(
                generated_at=updated_timestamp,
                version_id=version_id,
                checksum=checksum,
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

    def _prepare_branch_plan(
        self,
        *,
        branch_name: str,
        scenes: Mapping[str, Any],
        schema_version: int | None,
        generated_at: datetime | None,
        expected_base_version: str | None,
    ) -> tuple[SceneBranchPlanResponse, dict[str, Any]]:
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
            serialisable_target_any = json.loads(
                json.dumps(migrated_scenes, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(serialisable_target_any, dict):
            raise ValueError("Serialised branch data must be a mapping.")

        serialisable_target = cast(dict[str, Any], serialisable_target_any)

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

        plan = SceneBranchPlanResponse(
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

        return plan, serialisable_target

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

        plan, _ = self._prepare_branch_plan(
            branch_name=branch_name,
            scenes=scenes,
            schema_version=schema_version,
            generated_at=generated_at,
            expected_base_version=expected_base_version,
        )
        return plan

    def create_branch(
        self,
        *,
        branch_name: str,
        scenes: Mapping[str, Any],
        schema_version: int | None = None,
        generated_at: datetime | None = None,
        expected_base_version: str | None = None,
    ) -> SceneBranchResource:
        """Persist a branch definition and return its metadata."""

        plan, serialisable_target = self._prepare_branch_plan(
            branch_name=branch_name,
            scenes=scenes,
            schema_version=schema_version,
            generated_at=generated_at,
            expected_base_version=expected_base_version,
        )

        identifier = _slugify_branch_name(plan.branch_name)
        if not identifier:
            raise ValueError(
                "Branch name must include alphanumeric characters to form an identifier."
            )

        record = SceneBranchRecord(
            identifier=identifier,
            name=plan.branch_name,
            created_at=datetime.now(timezone.utc),
            plan=plan,
            scenes=serialisable_target,
        )

        try:
            self._branch_store.save(record)
        except FileExistsError as exc:
            raise FileExistsError(f"Branch '{identifier}' already exists.") from exc
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

        return _build_branch_resource(record)

    def list_branches(self) -> SceneBranchListResponse:
        """Return persisted branch definitions."""

        try:
            records = self._branch_store.list()
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        return SceneBranchListResponse(
            data=[_build_branch_resource(record) for record in records]
        )

    def get_branch(self, identifier: str) -> SceneBranchDetailResponse:
        """Return the persisted branch definition identified by ``identifier``."""

        try:
            record = self._branch_store.load(identifier)
        except FileNotFoundError as exc:
            raise FileNotFoundError(str(exc)) from exc
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        return _build_branch_detail(record)

    def delete_branch(self, identifier: str) -> None:
        """Remove the branch definition identified by ``identifier``."""

        try:
            self._branch_store.delete(identifier)
        except FileNotFoundError as exc:
            raise FileNotFoundError(str(exc)) from exc
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

    def create_backup(
        self,
        *,
        destination_dir: Path,
        export_format: ExportFormat = ExportFormat.PRETTY,
        uploaders: Sequence[BackupUploader] | None = None,
    ) -> SceneBackupResult:
        """Write the current scene dataset to ``destination_dir``."""

        export = self.export_scenes()
        resolved_uploaders: tuple[BackupUploader, ...]
        if uploaders is not None:
            resolved_uploaders = tuple(uploaders)
        else:
            resolved_uploaders = self._automatic_backup_uploaders

        return self._write_backup(
            destination_dir=destination_dir,
            dataset=export.scenes,
            generated_at=export.generated_at,
            version_id=export.metadata.version_id,
            checksum=export.metadata.checksum,
            export_format=export_format,
            uploaders=resolved_uploaders,
        )

    def _maybe_create_automatic_backup(
        self,
        *,
        dataset: Mapping[str, Any],
        generated_at: datetime,
        version_id: str,
        checksum: str,
    ) -> None:
        destination = self._automatic_backup_dir
        if destination is None and not self._automatic_backup_uploaders:
            return

        if destination is not None:
            self._write_backup(
                destination_dir=destination,
                dataset=dataset,
                generated_at=generated_at,
                version_id=version_id,
                checksum=checksum,
                export_format=self._automatic_backup_export_format,
                uploaders=self._automatic_backup_uploaders,
            )

            retention = self._automatic_backup_retention
            if retention is not None:
                self._prune_automatic_backups(destination, keep=retention)
        else:
            self._dispatch_backup_upload(
                uploaders=self._automatic_backup_uploaders,
                filename=_build_backup_filename(version_id),
                content=self._serialise_backup_dataset(
                    dataset, export_format=self._automatic_backup_export_format
                ),
                version_id=version_id,
                checksum=checksum,
                generated_at=generated_at,
            )

    def _write_backup(
        self,
        *,
        destination_dir: Path,
        dataset: Mapping[str, Any],
        generated_at: datetime,
        version_id: str,
        checksum: str,
        export_format: ExportFormat,
        uploaders: Sequence[BackupUploader],
    ) -> SceneBackupResult:
        content = self._serialise_backup_dataset(dataset, export_format=export_format)

        try:
            destination_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to prepare backup directory '{destination_dir}'."
            ) from exc

        filename = _build_backup_filename(version_id)
        backup_path = destination_dir / filename

        try:
            with backup_path.open("w", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as exc:
            raise RuntimeError(f"Failed to write backup to '{backup_path}'.") from exc

        self._dispatch_backup_upload(
            uploaders=uploaders,
            filename=filename,
            content=content,
            version_id=version_id,
            checksum=checksum,
            generated_at=generated_at,
        )

        return SceneBackupResult(
            path=backup_path,
            version_id=version_id,
            checksum=checksum,
            generated_at=generated_at,
        )

    def _serialise_backup_dataset(
        self, dataset: Mapping[str, Any], *, export_format: ExportFormat
    ) -> str:
        try:
            serialisable = json.loads(json.dumps(dataset, ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Scene data could not be serialised to JSON.") from exc

        if not isinstance(serialisable, dict):
            raise RuntimeError("Scene data must be a JSON object.")

        dumps = _dumps_for_export_format(export_format)
        return dumps(serialisable)

    def _dispatch_backup_upload(
        self,
        *,
        uploaders: Sequence[BackupUploader],
        filename: str,
        content: str,
        version_id: str,
        checksum: str,
        generated_at: datetime,
    ) -> None:
        if not uploaders:
            return

        payload = content.encode("utf-8")
        metadata = BackupUploadMetadata(
            filename=filename,
            version_id=version_id,
            checksum=checksum,
            generated_at=generated_at,
        )

        for uploader in uploaders:
            uploader.upload(content=payload, metadata=metadata)

    def _prune_automatic_backups(self, destination: Path, *, keep: int) -> None:
        if keep < 1:
            return

        backups: list[tuple[float, str, Path]] = []
        for candidate in destination.glob("scene-backup-*.json"):
            if not candidate.is_file():
                continue
            try:
                mtime = candidate.stat().st_mtime
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to inspect automatic backup '{candidate}'."
                ) from exc
            backups.append((mtime, candidate.name, candidate))

        backups.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)

        for _, _, path in backups[keep:]:
            try:
                path.unlink()
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to prune automatic backup '{path}'."
                ) from exc

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


def create_app(
    scene_service: SceneService | None = None,
    *,
    project_service: ProjectService | None = None,
    project_template_service: ProjectTemplateService | None = None,
    user_service: UserService | None = None,
    marketplace_service: MarketplaceService | None = None,
    forum_service: ForumService | None = None,
    settings: SceneApiSettings | None = None,
) -> FastAPI:
    """Create a FastAPI app exposing the scene management endpoints."""

    resolved_settings = settings or SceneApiSettings.from_env()

    repository = SceneRepository(
        package=resolved_settings.scene_package,
        resource_name=resolved_settings.scene_resource_name,
        path=resolved_settings.scene_path,
    )

    service = scene_service
    if service is None:
        branch_store = SceneBranchStore(root=resolved_settings.branch_root)
        automatic_backup_uploaders: list[BackupUploader] = []
        if resolved_settings.automatic_backup_s3_bucket:
            automatic_backup_uploaders.append(
                S3BackupUploader(
                    bucket=resolved_settings.automatic_backup_s3_bucket,
                    prefix=resolved_settings.automatic_backup_s3_prefix,
                    region_name=resolved_settings.automatic_backup_s3_region,
                    endpoint_url=resolved_settings.automatic_backup_s3_endpoint_url,
                )
            )
        service = SceneService(
            repository=repository,
            branch_store=branch_store,
            automatic_backup_dir=resolved_settings.automatic_backup_dir,
            automatic_backup_retention=resolved_settings.automatic_backup_retention,
            automatic_backup_uploaders=automatic_backup_uploaders,
        )

    user = user_service
    if user is None and resolved_settings.user_root is not None:
        user_store = UserAccountStore(root=resolved_settings.user_root)
        user = UserService(store=user_store)

    project_store: SceneProjectStore | None = None
    if resolved_settings.project_root is not None:
        project_store = SceneProjectStore(root=resolved_settings.project_root)

    project = project_service
    if project is None and project_store is not None:
        project = ProjectService(store=project_store, user_service=user)

    template_service = project_template_service
    if (
        template_service is None
        and project is not None
        and resolved_settings.project_template_root is not None
    ):
        template_store = SceneProjectStore(root=resolved_settings.project_template_root)
        template_service = ProjectTemplateService(
            template_store=template_store,
            project_service=project,
        )

    marketplace = marketplace_service
    if marketplace is None:
        marketplace_store = MarketplaceStore(root=resolved_settings.marketplace_root)
        marketplace = MarketplaceService(store=marketplace_store)

    forum = forum_service
    if forum is None:
        forum_store = ForumStore(root=resolved_settings.forum_root)
        forum = ForumService(store=forum_store)

    playtest_manager = PlaytestManager(
        repository=repository,
        project_service=project,
    )

    active_playtest_sessions: dict[str, PlaytestSession] = {}

    active_scene_path = repository.path

    def _enforce_scene_permission(
        acting_user_id: str | None,
        *,
        allowed_roles: Sequence[CollaboratorRole],
        action: str,
    ) -> None:
        if project is None or active_scene_path is None:
            return

        try:
            project.require_scene_dataset_permission(
                scene_path=active_scene_path,
                acting_user_id=acting_user_id,
                allowed_roles=allowed_roles,
                action=action,
            )
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    tags_metadata = [
        {
            "name": "Scenes",
            "description": (
                "CRUD operations, validation, analytics, and import/export for "
                "scripted adventure scenes."
            ),
        },
        {
            "name": "Scene Branches",
            "description": (
                "Create and manage experimental scene branches for iterative "
                "story development."
            ),
        },
        {
            "name": "Search",
            "description": (
                "Full-text search with filtering across the scripted scene "
                "catalogue."
            ),
        },
        {
            "name": "Projects",
            "description": (
                "Manage adventure projects, including asset inventories and "
                "collaborator rosters exposed to editor tooling."
            ),
        },
        {
            "name": "Marketplace",
            "description": (
                "Publish and discover community-contributed adventure "
                "datasets for reuse."
            ),
        },
        {
            "name": "Forums",
            "description": (
                "Discuss adventure design, share feedback, and coordinate "
                "with other authors."
            ),
        },
        {
            "name": "Users",
            "description": (
                "Manage user profiles used for collaboration and access "
                "control within the editor ecosystem."
            ),
        },
        {
            "name": "Project Templates",
            "description": (
                "Discover reusable templates and instantiate new projects "
                "from curated datasets."
            ),
        },
        {
            "name": "Playtest",
            "description": (
                "Control live playtest sessions, transcripts, and the "
                "embedded WebSocket preview."
            ),
        },
    ]

    app = FastAPI(
        title="Text Adventure Scene API",
        version="0.1.0",
        description=(
            "HTTP API powering the text adventure editor and analytics suite. "
            "The service exposes endpoints for scripted scenes, validation "
            "reports, search, project assets, and template management."
        ),
        openapi_tags=tags_metadata,
    )

    @app.get(
        "/api/scenes",
        response_model=SceneListResponse,
        tags=["Scenes"],
    )
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

    @app.get(
        "/api/scenes/{scene_id}",
        response_model=SceneDetailResponse,
        tags=["Scenes"],
    )
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

    @app.post(
        "/api/scenes",
        response_model=SceneMutationResponse,
        status_code=201,
        tags=["Scenes"],
    )
    def create_scene_endpoint(
        payload: SceneCreateRequest,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the scene mutation."
            ),
        ),
    ) -> SceneMutationResponse:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="create scenes",
        )
        try:
            return service.create_scene(
                scene_id=payload.id,
                scene=payload.scene,
                schema_version=payload.schema_version,
                expected_version_id=payload.expected_version_id,
            )
        except SceneAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except SceneVersionConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "current_version_id": exc.current_version_id,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put(
        "/api/scenes/{scene_id}",
        response_model=SceneMutationResponse,
        tags=["Scenes"],
    )
    def update_scene_endpoint(
        scene_id: str,
        payload: SceneUpdateRequest,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the scene mutation."
            ),
        ),
    ) -> SceneMutationResponse:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="update scenes",
        )
        try:
            return service.update_scene(
                scene_id=scene_id,
                scene=payload.scene,
                schema_version=payload.schema_version,
                expected_version_id=payload.expected_version_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SceneVersionConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "current_version_id": exc.current_version_id,
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete(
        "/api/scenes/{scene_id}",
        response_model=SceneDeleteResponse,
        tags=["Scenes"],
    )
    def delete_scene_endpoint(
        scene_id: str,
        expected_version_id: str | None = Query(
            None,
            description=(
                "Optional scene dataset version identifier used for optimistic "
                "concurrency checks."
            ),
        ),
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the scene mutation."
            ),
        ),
    ) -> SceneDeleteResponse:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="delete scenes",
        )
        try:
            return service.delete_scene(
                scene_id=scene_id, expected_version_id=expected_version_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SceneVersionConflictError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": str(exc),
                    "current_version_id": exc.current_version_id,
                },
            ) from exc
        except SceneDependencyError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": str(exc),
                    "references": [
                        {"scene_id": ref.scene_id, "command": ref.command}
                        for ref in exc.references
                    ],
                },
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/scenes/graph",
        response_model=SceneGraphResponse,
        tags=["Scenes"],
    )
    def get_scene_graph(
        start_scene: str | None = Query(
            None,
            description=(
                "Optional scene identifier to treat as the starting node when "
                "deriving graph metadata."
            ),
        ),
    ) -> SceneGraphResponse:
        try:
            return service.get_scene_graph(start_scene=start_scene)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/search",
        response_model=SceneSearchResponse,
        tags=["Search"],
    )
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

    @app.get(
        "/api/scenes/validate",
        response_model=SceneValidationResponse,
        tags=["Scenes"],
    )
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

    def _handle_scene_export(
        ids_param: str | None, format_param: ExportFormat
    ) -> FormattedJSONResponse:
        try:
            parsed_ids = _parse_scene_id_filter(ids_param)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            export_format = (
                format_param
                if isinstance(format_param, ExportFormat)
                else ExportFormat(format_param)
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

    def _handle_scene_import(payload: SceneImportRequest) -> SceneImportResponse:
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

    @app.get(
        "/api/export/scenes",
        response_model=None,
        tags=["Scenes"],
    )
    def export_scenes_legacy(
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
        return _handle_scene_export(ids, format)

    @app.get(
        "/api/scenes/export",
        response_model=None,
        tags=["Scenes"],
    )
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
        return _handle_scene_export(ids, format)

    @app.post(
        "/api/import/scenes",
        response_model=SceneImportResponse,
        tags=["Scenes"],
    )
    def import_scenes_legacy(payload: SceneImportRequest) -> SceneImportResponse:
        return _handle_scene_import(payload)

    @app.post(
        "/api/scenes/import",
        response_model=SceneImportResponse,
        tags=["Scenes"],
    )
    def import_scenes(payload: SceneImportRequest) -> SceneImportResponse:
        return _handle_scene_import(payload)

    @app.post(
        "/api/scenes/rollback",
        response_model=SceneRollbackResponse,
        tags=["Scenes"],
    )
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

    @app.get(
        "/api/scenes/branches",
        response_model=SceneBranchListResponse,
        tags=["Scene Branches"],
    )
    def list_branches() -> SceneBranchListResponse:
        try:
            return service.list_branches()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/scenes/branches/{branch_id}",
        response_model=SceneBranchDetailResponse,
        tags=["Scene Branches"],
    )
    def get_branch(branch_id: str) -> SceneBranchDetailResponse:
        try:
            return service.get_branch(branch_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/scenes/branches",
        response_model=SceneBranchResource,
        status_code=201,
        tags=["Scene Branches"],
    )
    def create_branch(
        payload: SceneBranchCreateRequest,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the branch mutation."
            ),
        ),
    ) -> SceneBranchResource:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="create branches",
        )
        try:
            return service.create_branch(
                branch_name=payload.branch_name,
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                generated_at=payload.generated_at,
                expected_base_version=payload.base_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete(
        "/api/scenes/branches/{branch_id}",
        response_model=None,
        status_code=204,
        tags=["Scene Branches"],
    )
    def delete_branch(
        branch_id: str,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the branch mutation."
            ),
        ),
    ) -> None:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="delete branches",
        )
        try:
            service.delete_branch(branch_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/scenes/branches/plan",
        response_model=SceneBranchPlanResponse,
        tags=["Scene Branches"],
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

    @app.post(
        "/api/scenes/diff",
        response_model=SceneDiffResponse,
        tags=["Scenes"],
    )
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

    @app.get(
        "/api/projects",
        response_model=AdventureProjectListResponse,
        tags=["Projects"],
    )
    def list_projects() -> AdventureProjectListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.list_projects()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/projects/{project_id}",
        response_model=AdventureProjectDetailResponse,
        tags=["Projects"],
    )
    def get_project(project_id: str) -> AdventureProjectDetailResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.get_project(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/projects/{project_id}/export",
        tags=["Projects"],
    )
    def export_project_archive(project_id: str) -> BinaryResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            archive = project.export_project(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        headers = {
            "content-disposition": f'attachment; filename="{archive.filename}"',
            "content-length": str(archive.size),
            "x-textadventure-project-id": archive.project_id,
            "x-textadventure-project-version": archive.version_id,
            "x-textadventure-project-checksum": archive.checksum,
        }

        return BinaryResponse(
            content=archive.content,
            media_type=archive.content_type,
            headers=headers,
        )

    @app.get(
        "/api/projects/{project_id}/assets",
        response_model=ProjectAssetListResponse,
        tags=["Projects"],
    )
    def list_project_assets(project_id: str) -> ProjectAssetListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.list_project_assets(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        tags=["Projects"],
    )
    def get_project_asset(project_id: str, asset_path: str) -> BinaryResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            asset = project.fetch_project_asset(project_id, asset_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        headers = {"content-disposition": f'attachment; filename="{asset.filename}"'}
        media_type = asset.content_type or "application/octet-stream"
        return BinaryResponse(
            content=asset.content, media_type=media_type, headers=headers
        )

    @app.put(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        response_model=ProjectAssetResource,
        tags=["Projects"],
    )
    def upload_project_asset(
        project_id: str,
        asset_path: str,
        payload: ProjectAssetUploadRequest,
        acting_user_id: str | None = Query(
            None,
            description=("Identifier of the collaborator performing the upload."),
        ),
    ) -> ProjectAssetResource:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            content = payload.decoded_content()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            return project.store_project_asset(
                project_id,
                asset_path,
                content,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        status_code=204,
        tags=["Projects"],
    )
    def delete_project_asset(
        project_id: str,
        asset_path: str,
        acting_user_id: str | None = Query(
            None,
            description=("Identifier of the collaborator performing the deletion."),
        ),
    ) -> None:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            project.delete_project_asset(
                project_id,
                asset_path,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/projects/{project_id}/collaborators",
        response_model=ProjectCollaboratorListResponse,
        tags=["Projects"],
    )
    def list_project_collaborators(
        project_id: str,
    ) -> ProjectCollaboratorListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.list_project_collaborators(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put(
        "/api/projects/{project_id}/collaborators",
        response_model=ProjectCollaboratorListResponse,
        tags=["Projects"],
    )
    def replace_project_collaborators(
        project_id: str,
        payload: ProjectCollaboratorUpdateRequest,
        acting_user_id: str | None = Query(
            None,
            description=("Identifier of the collaborator performing the update."),
        ),
    ) -> ProjectCollaboratorListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.replace_project_collaborators(
                project_id,
                payload.collaborators,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/projects/{project_id}/collaboration/sessions",
        response_model=ProjectCollaborationSessionListResponse,
        tags=["Projects"],
    )
    def list_project_collaboration_sessions(
        project_id: str,
    ) -> ProjectCollaborationSessionListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.list_collaboration_sessions(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/projects/{project_id}/collaboration/sessions",
        response_model=ProjectCollaborationSessionListResponse,
        tags=["Projects"],
    )
    def touch_project_collaboration_session(
        project_id: str,
        payload: ProjectCollaborationSessionRequest,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the join or heartbeat."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.touch_collaboration_session(
                project_id,
                acting_user_id=acting_user_id,
                session_id=payload.session_id,
                scene_id=payload.scene_id,
                ttl_seconds=payload.ttl_seconds,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.delete(
        "/api/projects/{project_id}/collaboration/sessions/{session_id}",
        response_model=ProjectCollaborationSessionListResponse,
        tags=["Projects"],
    )
    def delete_project_collaboration_session(
        project_id: str,
        session_id: str,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the session termination."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project is None:
            raise HTTPException(404, "Project management endpoints are not enabled.")

        try:
            return project.end_collaboration_session(
                project_id,
                session_id,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/marketplace/entries",
        response_model=MarketplaceEntryListResponse,
        tags=["Marketplace"],
    )
    def list_marketplace_entries(
        search: str | None = Query(
            None,
            description=(
                "Optional case-insensitive substring to filter by identifier, "
                "title, or description."
            ),
        ),
        tag: str | None = Query(
            None,
            description="Restrict results to entries tagged with the provided value.",
        ),
        page: int = Query(1, ge=1, description="Page number (1-indexed)."),
        page_size: int = Query(
            20,
            ge=1,
            le=100,
            description="Number of entries to include per page (maximum 100).",
        ),
    ) -> MarketplaceEntryListResponse:
        try:
            return marketplace.list_entries(
                search=search,
                tag=tag,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/marketplace/entries/{entry_id}",
        response_model=MarketplaceEntryResponse,
        tags=["Marketplace"],
    )
    def get_marketplace_entry(entry_id: str) -> MarketplaceEntryResponse:
        try:
            record = marketplace.get_entry(entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_marketplace_response(record)

    @app.get(
        "/api/marketplace/entries/{entry_id}/reviews",
        response_model=MarketplaceReviewListResponse,
        tags=["Marketplace"],
    )
    def list_marketplace_entry_reviews(
        entry_id: str,
    ) -> MarketplaceReviewListResponse:
        try:
            record = marketplace.get_entry(entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        ordered = _sort_reviews_newest_first(record.reviews)
        reviews = [_build_marketplace_review(review) for review in ordered]
        return MarketplaceReviewListResponse(
            data=reviews,
            average_rating=_compute_average_rating(record.reviews),
            review_count=len(record.reviews),
        )

    @app.post(
        "/api/marketplace/entries",
        response_model=MarketplaceEntryResponse,
        status_code=201,
        tags=["Marketplace"],
    )
    def publish_marketplace_entry(
        payload: MarketplaceEntryPublishRequest,
    ) -> MarketplaceEntryResponse:
        try:
            record = marketplace.publish_entry(payload)
        except MarketplaceEntryAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_marketplace_response(record)

    @app.post(
        "/api/marketplace/entries/{entry_id}/reviews",
        response_model=MarketplaceReview,
        status_code=201,
        tags=["Marketplace"],
    )
    def create_marketplace_entry_review(
        entry_id: str, payload: MarketplaceReviewCreateRequest
    ) -> MarketplaceReview:
        try:
            _, review = marketplace.add_review(entry_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_marketplace_review(review)

    @app.get(
        "/api/forums/threads",
        response_model=ForumThreadListResponse,
        tags=["Forums"],
    )
    def list_forum_threads(
        page: int = Query(1, ge=1),
        page_size: int = Query(
            20,
            ge=1,
            le=100,
            description="Number of threads to return per page (maximum 100).",
        ),
    ) -> ForumThreadListResponse:
        try:
            return forum.list_threads(page=page, page_size=page_size)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/forums/threads",
        response_model=ForumThreadDetail,
        status_code=201,
        tags=["Forums"],
    )
    def create_forum_thread(
        payload: ForumThreadCreateRequest,
    ) -> ForumThreadDetail:
        try:
            record = forum.create_thread(payload)
        except ForumThreadAlreadyExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_forum_thread_detail(record)

    @app.get(
        "/api/forums/threads/{thread_id}",
        response_model=ForumThreadDetail,
        tags=["Forums"],
    )
    def get_forum_thread(thread_id: str) -> ForumThreadDetail:
        try:
            record = forum.get_thread(thread_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_forum_thread_detail(record)

    @app.post(
        "/api/forums/threads/{thread_id}/posts",
        response_model=ForumPostResource,
        status_code=201,
        tags=["Forums"],
    )
    def create_forum_post(
        thread_id: str, payload: ForumPostCreateRequest
    ) -> ForumPostResource:
        try:
            post = forum.add_post(thread_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_forum_post(post)

    @app.get(
        "/api/users",
        response_model=UserProfileListResponse,
        tags=["Users"],
    )
    def list_users() -> UserProfileListResponse:
        if user is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user.list_users()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/users/{user_id}",
        response_model=UserProfileResource,
        tags=["Users"],
    )
    def get_user(user_id: str) -> UserProfileResource:
        if user is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user.get_user(user_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/users",
        response_model=UserProfileResource,
        status_code=201,
        tags=["Users"],
    )
    def create_user(payload: UserProfileCreateRequest) -> UserProfileResource:
        if user is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user.create_user(
                identifier=payload.id,
                display_name=payload.display_name,
                email=payload.email,
                bio=payload.bio,
            )
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.put(
        "/api/users/{user_id}",
        response_model=UserProfileResource,
        tags=["Users"],
    )
    def update_user(
        user_id: str, payload: UserProfileUpdateRequest
    ) -> UserProfileResource:
        if user is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        update_kwargs: dict[str, Any] = {}
        if "display_name" in payload.model_fields_set:
            update_kwargs["display_name"] = payload.display_name
        if "email" in payload.model_fields_set:
            update_kwargs["email"] = payload.email
        if "bio" in payload.model_fields_set:
            update_kwargs["bio"] = payload.bio

        try:
            return user.update_user(user_id, **update_kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/project-templates",
        response_model=AdventureProjectTemplateListResponse,
        tags=["Project Templates"],
    )
    def list_project_templates() -> AdventureProjectTemplateListResponse:
        if template_service is None:
            raise HTTPException(404, "Project template endpoints are not enabled.")

        try:
            return template_service.list_templates()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/project-templates/{template_id}/instantiate",
        response_model=AdventureProjectDetailResponse,
        status_code=201,
        tags=["Project Templates"],
    )
    def instantiate_project_template(
        template_id: str, payload: ProjectTemplateInstantiateRequest
    ) -> AdventureProjectDetailResponse:
        if template_service is None:
            raise HTTPException(404, "Project template endpoints are not enabled.")

        try:
            return template_service.instantiate_template(
                template_id,
                project_id=payload.project_id,
                name=payload.name,
                description=payload.description,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/playtest/sessions/{session_id}/transcript",
        response_model=PlaytestTranscriptResponse,
        tags=["Playtest"],
    )
    def get_playtest_transcript(session_id: str) -> PlaytestTranscriptResponse:
        session = active_playtest_sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Playtest session not found.")

        return PlaytestTranscriptResponse(
            session_id=session_id,
            entries=_build_playtest_transcript_entries(session),
        )

    @app.delete(
        "/api/playtest/sessions/{session_id}/transcript",
        status_code=204,
        tags=["Playtest"],
    )
    def clear_playtest_transcript(session_id: str) -> None:
        session = active_playtest_sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Playtest session not found.")

        session.clear_transcript()

    @app.websocket("/api/playtest")
    def playtest_endpoint(websocket: WebSocket) -> None:
        websocket.accept()

        initial_project_id = websocket.query_params.get("project_id")

        session_id = uuid.uuid4().hex

        try:
            try:
                session = playtest_manager.create_session(project_id=initial_project_id)
                initial_event = session.reset()
            except FileNotFoundError as exc:
                websocket.send_json(
                    _build_playtest_error_message(
                        "project-not-found", str(exc)
                    ).model_dump(mode="json")
                )
                websocket.close(code=4404)
                return
            except ValueError as exc:
                websocket.send_json(
                    _build_playtest_error_message(
                        "invalid-project", str(exc)
                    ).model_dump(mode="json")
                )
                websocket.close(code=4400)
                return
            except RuntimeError as exc:
                websocket.send_json(
                    _build_playtest_error_message("session-error", str(exc)).model_dump(
                        mode="json"
                    )
                )
                websocket.close(code=1011)
                return

            active_playtest_sessions[session_id] = session

            websocket.send_json(
                _build_playtest_event_message(
                    initial_event, session, session_id=session_id
                ).model_dump(mode="json")
            )

            while True:
                try:
                    payload = websocket.receive_json()
                except WebSocketDisconnect:
                    break

                if not isinstance(payload, Mapping):
                    websocket.send_json(
                        _build_playtest_error_message(
                            "invalid-message", "Payload must be a JSON object."
                        ).model_dump(mode="json")
                    )
                    continue

                raw_type = payload.get("type")
                if not isinstance(raw_type, str):
                    websocket.send_json(
                        _build_playtest_error_message(
                            "invalid-message", "Message type must be a string."
                        ).model_dump(mode="json")
                    )
                    continue

                message_type = raw_type.strip().lower()

                if message_type == "player_input":
                    command_value = payload.get("input", "")
                    if not isinstance(command_value, str):
                        websocket.send_json(
                            _build_playtest_error_message(
                                "invalid-message", "Player input must be a string."
                            ).model_dump(mode="json")
                        )
                        continue
                    try:
                        event = session.apply_player_input(command_value)
                    except Exception as exc:  # pragma: no cover - surfaced to client
                        websocket.send_json(
                            _build_playtest_error_message(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    websocket.send_json(
                        _build_playtest_event_message(
                            event, session, session_id=session_id
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "reset":
                    try:
                        event = session.reset()
                    except Exception as exc:  # pragma: no cover - surfaced to client
                        websocket.send_json(
                            _build_playtest_error_message(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    websocket.send_json(
                        _build_playtest_event_message(
                            event, session, session_id=session_id
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "configure":
                    project_value = payload.get("project_id")
                    if not isinstance(project_value, str) or not project_value.strip():
                        websocket.send_json(
                            _build_playtest_error_message(
                                "invalid-project",
                                "Project identifier must be a non-empty string.",
                            ).model_dump(mode="json")
                        )
                        continue
                    try:
                        new_session = playtest_manager.create_session(
                            project_id=project_value
                        )
                        event = new_session.reset()
                    except FileNotFoundError as exc:
                        websocket.send_json(
                            _build_playtest_error_message(
                                "project-not-found", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except ValueError as exc:
                        websocket.send_json(
                            _build_playtest_error_message(
                                "invalid-project", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except RuntimeError as exc:
                        websocket.send_json(
                            _build_playtest_error_message(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    session = new_session
                    active_playtest_sessions[session_id] = session
                    websocket.send_json(
                        _build_playtest_event_message(
                            event, session, session_id=session_id
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "transcript":
                    websocket.send_json(
                        _build_playtest_transcript_message(
                            session_id, session
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "clear_transcript":
                    session.clear_transcript()
                    websocket.send_json(
                        _build_playtest_transcript_message(
                            session_id, session
                        ).model_dump(mode="json")
                    )
                    continue

                websocket.send_json(
                    _build_playtest_error_message(
                        "unknown-message",
                        f"Unsupported message type '{message_type}'.",
                    ).model_dump(mode="json")
                )
        finally:
            active_playtest_sessions.pop(session_id, None)

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
    item_flow = analyse_item_flow(cast(Mapping[str, _AnalyticsSceneLike], scenes))

    error_scenes: set[str] = set(report.scenes_missing_description)
    error_scenes.update(scene for scene, _ in report.transitions_missing_narration)
    error_scenes.update(
        scene for scene, _, _ in report.conditional_overrides_missing_narration
    )
    error_scenes.update(
        scene for scene, _, _ in report.transitions_with_unknown_targets
    )
    for detail in item_flow.items:
        if detail.is_missing_source:
            error_scenes.update(reference.scene for reference in detail.requirements)
            error_scenes.update(reference.scene for reference in detail.consumptions)

    warning_scenes: set[str] = set(
        scene for scene, _ in report.choices_missing_description
    )
    warning_scenes.update(
        scene for scene, _ in report.gated_transitions_missing_failure
    )
    for detail in item_flow.items:
        if detail.is_orphaned:
            warning_scenes.update(reference.scene for reference in detail.sources)

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
    unknown_targets = [
        SceneTargetIssueResource(scene_id=scene, command=command, target=target)
        for scene, command, target in report.transitions_with_unknown_targets
    ]

    return QualityIssuesResource(
        issue_count=report.issue_count,
        scenes_missing_description=list(report.scenes_missing_description),
        choices_missing_description=choices,
        transitions_missing_narration=transitions,
        gated_transitions_missing_failure=gated,
        conditional_overrides_missing_narration=overrides,
        transitions_with_unknown_target=unknown_targets,
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


@dataclass(frozen=True)
class PlaytestTranscriptEntry:
    """Single turn recorded during a live playtest session."""

    turn: int
    player_input: str | None
    event: StoryEvent


class PlaytestTranscriptRecorder:
    """Accumulates a chronological transcript of playtest turns."""

    def __init__(self) -> None:
        self._entries: list[PlaytestTranscriptEntry] = []
        self._turn = 0

    def reset(self) -> None:
        """Clear the recorded transcript and reset the turn counter."""

        self._entries.clear()
        self._turn = 0

    def record(self, *, player_input: str | None, event: StoryEvent) -> None:
        """Append a new entry describing the latest turn."""

        self._turn += 1
        self._entries.append(
            PlaytestTranscriptEntry(
                turn=self._turn,
                player_input=player_input,
                event=event,
            )
        )

    def entries(self) -> tuple[PlaytestTranscriptEntry, ...]:
        """Return an immutable view of the recorded transcript."""

        return tuple(self._entries)


class PlaytestSession:
    """Manage story state for a single live playtest connection."""

    def __init__(self, engine_factory: Callable[[], StoryEngine]) -> None:
        self._engine_factory = engine_factory
        self._engine = engine_factory()
        self._world = WorldState()
        self._transcript = PlaytestTranscriptRecorder()

    def clear_transcript(self) -> None:
        """Clear the recorded transcript without mutating world state."""

        self._transcript.reset()

    def reset(self) -> StoryEvent:
        """Reset the session and return the initial narrative event."""

        new_engine = self._engine_factory()
        new_world = WorldState()

        previous_engine = self._engine
        previous_world = self._world

        self._engine = new_engine
        self._world = new_world
        self._transcript.reset()

        try:
            return self._produce_event(None)
        except Exception:  # pragma: no cover - propagated to caller
            self._engine = previous_engine
            self._world = previous_world
            raise

    def apply_player_input(self, player_input: str) -> StoryEvent:
        """Advance the story using ``player_input`` and return the next event."""

        return self._produce_event(player_input)

    def world_snapshot(self) -> PlaytestWorldStateResource:
        """Return a serialisable snapshot of the current world state."""

        return PlaytestWorldStateResource(
            location=self._world.location,
            inventory=sorted(self._world.inventory),
            history=list(self._world.history),
            recent_actions=list(self._world.recent_actions()),
            recent_observations=list(self._world.recent_observations()),
            queued_messages=_build_queued_message_resources(self._engine),
        )

    def transcript(self) -> tuple[PlaytestTranscriptEntry, ...]:
        """Return the currently recorded playtest transcript."""

        return self._transcript.entries()

    def _produce_event(self, player_input: str | None) -> StoryEvent:
        if player_input is not None:
            command_text = str(player_input)
            trimmed = command_text.strip()
            if trimmed:
                self._world.remember_action(trimmed)
        else:
            command_text = None

        event = self._engine.propose_event(self._world, player_input=command_text)
        self._world.remember_observation(event.narration)
        self._transcript.record(player_input=command_text, event=event)
        return event


class PlaytestManager:
    """Factory for creating playtest sessions bound to specific datasets."""

    def __init__(
        self,
        repository: "SceneRepository",
        *,
        project_service: "ProjectService" | None = None,
    ) -> None:
        self._repository = repository
        self._project_service = project_service

    def create_session(self, *, project_id: str | None = None) -> PlaytestSession:
        """Return a new playtest session optionally scoped to ``project_id``."""

        resolved_project_id = self._normalise_project_identifier(project_id)

        def _engine_factory() -> StoryEngine:
            definitions = self._load_scene_definitions(project_id=resolved_project_id)
            scenes = load_scenes_from_mapping(definitions)
            base_engine = ScriptedStoryEngine(scenes=scenes)
            return MultiAgentCoordinator(
                ScriptedStoryAgent("scripted-primary", base_engine)
            )

        return PlaytestSession(_engine_factory)

    def _load_scene_definitions(self, *, project_id: str | None) -> Mapping[str, Any]:
        if project_id is None:
            definitions, _ = self._repository.load()
            return dict(definitions)

        if self._project_service is None:
            raise FileNotFoundError(
                "Project playtesting is not enabled for this server instance."
            )

        response = self._project_service.get_project(project_id)
        return dict(response.scenes)

    @staticmethod
    def _normalise_project_identifier(identifier: str | None) -> str | None:
        if identifier is None:
            return None
        if not isinstance(identifier, str):
            raise ValueError("Project identifier must be provided as a string.")
        trimmed = identifier.strip()
        return trimmed or None


def _build_memory_request_resource(
    request: MemoryRequest | None,
) -> MemoryRequestResource | None:
    if request is None:
        return None
    return MemoryRequestResource(
        action_limit=request.action_limit,
        observation_limit=request.observation_limit,
    )


def _build_queued_message_resources(engine: StoryEngine) -> list[QueuedMessageResource]:
    debug_snapshot = getattr(engine, "debug_snapshot", None)
    if not callable(debug_snapshot):
        return []

    snapshot = debug_snapshot()
    resources: list[QueuedMessageResource] = []
    for message in getattr(snapshot, "queued_messages", ()):  # type: ignore[attr-defined]
        if not isinstance(message, QueuedAgentMessage):
            continue
        resources.append(
            QueuedMessageResource(
                origin_agent=message.origin_agent,
                trigger_kind=message.trigger_kind,
                player_input=message.player_input,
                metadata=dict(message.metadata),
                memory_request=_build_memory_request_resource(message.memory_request),
            )
        )
    return resources


def _build_playtest_event_resource(event: StoryEvent) -> PlaytestEventResource:
    return PlaytestEventResource(
        narration=event.narration,
        choices=[
            ChoiceResource(command=choice.command, description=choice.description)
            for choice in event.choices
        ],
        metadata=dict(cast(Mapping[str, str], event.metadata)),
        has_choices=event.has_choices,
    )


def _build_playtest_event_message(
    event: StoryEvent,
    session: PlaytestSession,
    *,
    session_id: str,
) -> PlaytestEventMessage:
    return PlaytestEventMessage(
        type="event",
        session_id=session_id,
        event=_build_playtest_event_resource(event),
        world=session.world_snapshot(),
    )


def _build_playtest_transcript_entries(
    session: PlaytestSession,
) -> list["PlaytestTranscriptEntryResource"]:
    entries: list[PlaytestTranscriptEntryResource] = []
    for entry in session.transcript():
        entries.append(
            PlaytestTranscriptEntryResource(
                turn=entry.turn,
                player_input=entry.player_input,
                event=_build_playtest_event_resource(entry.event),
            )
        )
    return entries


def _build_playtest_transcript_message(
    session_id: str, session: PlaytestSession
) -> "PlaytestTranscriptMessage":
    return PlaytestTranscriptMessage(
        type="transcript",
        session_id=session_id,
        entries=_build_playtest_transcript_entries(session),
    )


def _build_playtest_error_message(code: str, message: str) -> PlaytestErrorMessage:
    return PlaytestErrorMessage(type="error", code=str(code), message=str(message))


class ChoiceResource(BaseModel):
    """Representation of a single scene choice."""

    command: str
    description: str


class MemoryRequestResource(BaseModel):
    """Description of a queued agent memory request."""

    action_limit: int | None = None
    observation_limit: int | None = None


class QueuedMessageResource(BaseModel):
    """Metadata describing a queued coordinator message."""

    origin_agent: str
    trigger_kind: str
    player_input: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    memory_request: MemoryRequestResource | None = None


class PlaytestWorldStateResource(BaseModel):
    """Summary of the playtest world state surfaced via WebSocket."""

    location: str
    inventory: list[str] = Field(default_factory=list)
    history: list[str] = Field(default_factory=list)
    recent_actions: list[str] = Field(default_factory=list)
    recent_observations: list[str] = Field(default_factory=list)
    queued_messages: list[QueuedMessageResource] = Field(default_factory=list)


class PlaytestEventResource(BaseModel):
    """Narrative event broadcast to live preview clients."""

    narration: str
    choices: list[ChoiceResource] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    has_choices: bool


class PlaytestEventMessage(BaseModel):
    """Envelope describing an event message pushed over the WebSocket."""

    type: Literal["event"]
    session_id: str
    event: PlaytestEventResource
    world: PlaytestWorldStateResource


class PlaytestErrorMessage(BaseModel):
    """Error payload returned for invalid playtest commands."""

    type: Literal["error"]
    code: str
    message: str


class PlaytestTranscriptEntryResource(BaseModel):
    """Serialized transcript entry for HTTP and WebSocket responses."""

    turn: int
    player_input: str | None = None
    event: PlaytestEventResource


class PlaytestTranscriptMessage(BaseModel):
    """WebSocket payload returning the current transcript entries."""

    type: Literal["transcript"]
    session_id: str
    entries: list[PlaytestTranscriptEntryResource] = Field(default_factory=list)


class PlaytestTranscriptResponse(BaseModel):
    """HTTP response returning the recorded playtest transcript."""

    session_id: str
    entries: list[PlaytestTranscriptEntryResource] = Field(default_factory=list)


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


class SceneMutationResponse(BaseModel):
    """Response payload describing the outcome of a scene mutation."""

    data: SceneResource
    validation: SceneValidation | None = None
    version: SceneVersionInfo


class SceneDeleteResponse(BaseModel):
    """Response payload returned after deleting a scene definition."""

    scene_id: str
    version: SceneVersionInfo


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


def _find_scene_references(
    scene_id: str, scenes: Mapping[str, Any]
) -> list[SceneReference]:
    """Return transitions that reference ``scene_id`` from other scenes."""

    references: list[SceneReference] = []
    for candidate_id, scene in scenes.items():
        if candidate_id == scene_id:
            continue

        transitions = getattr(scene, "transitions", {})
        for command, transition in transitions.items():
            target = getattr(transition, "target", None)
            if target == scene_id:
                references.append(
                    SceneReference(scene_id=candidate_id, command=command)
                )

    references.sort(key=lambda entry: (entry.scene_id, entry.command))
    return references


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

    for candidate_scene, command, target in report.transitions_with_unknown_targets:
        if candidate_scene == scene_id:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="unknown_transition_target",
                    message=(
                        f"Transition '{command}' targets unknown scene '{target}'."
                    ),
                    path=f"transitions.{command}.target",
                )
            )

    issues.sort(key=lambda issue: (issue.path, issue.code))
    return issues
