"""Scene-related Pydantic models for the text adventure API.

This module contains all Pydantic model definitions related to scenes,
including scene summaries, graphs, search, validation, import/export,
versioning, branching, comments, and detailed scene resources.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator

from .common import DiffStatus, Pagination, ValidationStatus
from ...search import FieldType


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
    duplicate_choice_commands: list[SceneCommandIssueResource] = Field(
        default_factory=list
    )
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
    items_with_unreachable_sources: list[str] = Field(default_factory=list)


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


class SceneReferenceResource(BaseModel):
    """Reference indicating another scene points at the target scene."""

    scene_id: str
    command: str


class SceneReferenceListResponse(BaseModel):
    """Listing of references for a particular scene identifier."""

    scene_id: str
    data: tuple[SceneReferenceResource, ...]


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


class SceneCommentLocationType(str, Enum):
    """Enumerated locations where inline scene comments can be attached."""

    TRANSITION_NARRATION = "transition_narration"
    TRANSITION_FAILURE_NARRATION = "transition_failure_narration"


class SceneCommentLocation(BaseModel):
    """Location metadata describing where an inline comment is anchored."""

    type: SceneCommentLocationType = Field(
        ..., description="Semantic identifier describing the comment target."
    )
    choice_command: str = Field(
        ..., description="Player command associated with the transition narration."
    )

    @field_validator("choice_command")
    @classmethod
    def _validate_choice_command(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("choice_command must not be empty.")
        return trimmed


class SceneCommentResource(BaseModel):
    """Representation of an individual inline comment."""

    id: str = Field(..., description="Stable identifier for the comment entry.")
    author_id: str | None = Field(
        None, description="Optional collaborator identifier for the author."
    )
    author_display_name: str | None = Field(
        None, description="Optional display name resolved for the author."
    )
    body: str = Field(..., description="Markdown formatted comment body.")
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the comment was created."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Comment body must not be empty.")
        return trimmed


class SceneCommentThreadResource(BaseModel):
    """Inline comment thread with associated discussion entries."""

    id: str = Field(..., description="Stable identifier for the comment thread.")
    scene_id: str = Field(
        ..., description="Scene identifier the comment thread is associated with."
    )
    status: Literal["open", "resolved"] = Field(
        ..., description="Current resolution status for the thread."
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the thread was created."
    )
    updated_at: datetime = Field(
        ..., description="Timestamp for the most recent change within the thread."
    )
    resolved_at: datetime | None = Field(
        None, description="Timestamp when the thread was resolved, if applicable."
    )
    resolved_by: str | None = Field(
        None, description="Optional collaborator identifier that resolved the thread."
    )
    location: SceneCommentLocation = Field(
        ..., description="Location metadata describing the thread anchor."
    )
    comments: list[SceneCommentResource] = Field(
        default_factory=list,
        description="Chronologically ordered list of comments within the thread.",
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("updated_at")
    def _serialise_updated_at(self, value: datetime) -> str:
        return value.isoformat()

    @field_serializer("resolved_at")
    def _serialise_resolved_at(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None


class SceneCommentThreadListResponse(BaseModel):
    """Response payload enumerating inline comment threads for a scene."""

    project_id: str = Field(..., description="Identifier for the requested project.")
    scene_id: str = Field(
        ..., description="Scene identifier the comment threads were filtered against."
    )
    threads: list[SceneCommentThreadResource] = Field(
        default_factory=list,
        description="Ordered collection of comment threads for the scene.",
    )


class SceneCommentThreadCreateRequest(BaseModel):
    """Request body for creating a new inline comment thread."""

    location: SceneCommentLocation = Field(
        ...,
        description="Location metadata describing where the thread should be anchored.",
    )
    body: str = Field(
        ..., description="Markdown formatted body for the initial comment."
    )
    author_id: str | None = Field(
        None, description="Optional collaborator identifier for the author."
    )
    author_display_name: str | None = Field(
        None, description="Optional display name resolved for the author."
    )

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Comment body must not be empty.")
        return trimmed


class SceneCommentReplyRequest(BaseModel):
    """Request body for appending a comment to an existing thread."""

    body: str = Field(..., description="Markdown formatted reply body.")
    author_id: str | None = Field(
        None, description="Optional collaborator identifier for the author."
    )
    author_display_name: str | None = Field(
        None, description="Optional display name resolved for the author."
    )

    @field_validator("body")
    @classmethod
    def _validate_body(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Comment body must not be empty.")
        return trimmed


class SceneCommentResolveRequest(BaseModel):
    """Request payload for toggling the resolution state of a thread."""

    resolved: bool = Field(
        ..., description="Set to true to resolve the thread or false to reopen it."
    )


class ChoiceResource(BaseModel):
    """Representation of a single scene choice."""

    command: str
    description: str


class MemoryRequestResource(BaseModel):
    """Description of a queued agent memory request."""

    action_limit: int | None = None
    observation_limit: int | None = None


class TransitionResource(BaseModel):
    """Serialized representation of a transition."""

    narration: str
    target: str | None = None
    item: str | None = None
    requires: list[str] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)
    records: list[str] = Field(default_factory=list)
    failure_narration: str | None = None
    narration_overrides: list["NarrationOverrideResource"] = Field(default_factory=list)


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


class ValidationIssue(BaseModel):
    """Description of a validation issue detected for a scene."""

    severity: Literal["error", "warning"]
    code: str
    message: str
    path: str


class SceneValidation(BaseModel):
    """Collection of validation issues for a scene."""

    issues: list[ValidationIssue]


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


__all__ = [
    "SceneSummary",
    "SceneListResponse",
    "SceneGraphNodeResource",
    "SceneGraphEdgeResource",
    "SceneGraphResponse",
    "TextSpanResource",
    "FieldMatchResource",
    "SceneSearchResultResource",
    "SceneSearchResponse",
    "SceneCommandIssueResource",
    "SceneTargetIssueResource",
    "SceneOverrideIssueResource",
    "QualityIssuesResource",
    "SceneReachabilityResource",
    "ItemReferenceResource",
    "ItemFlowDetailsResource",
    "ItemFlowSummaryResource",
    "SceneValidationReport",
    "SceneValidationResponse",
    "SceneExportMetadata",
    "SceneExportResponse",
    "SceneImportRequest",
    "ImportStrategy",
    "SceneImportPlan",
    "SceneImportResponse",
    "SceneUpdateRequest",
    "SceneCreateRequest",
    "SceneDiffRequest",
    "SceneDiffEntry",
    "SceneDiffSummary",
    "SceneDiffResponse",
    "SceneReferenceResource",
    "SceneReferenceListResponse",
    "SceneVersionInfo",
    "SceneRollbackRequest",
    "SceneRollbackResponse",
    "SceneBranchPlanRequest",
    "SceneBranchPlanResponse",
    "SceneBranchResource",
    "SceneBranchListResponse",
    "SceneBranchCreateRequest",
    "SceneBranchDetailResponse",
    "SceneCommentLocationType",
    "SceneCommentLocation",
    "SceneCommentResource",
    "SceneCommentThreadResource",
    "SceneCommentThreadListResponse",
    "SceneCommentThreadCreateRequest",
    "SceneCommentReplyRequest",
    "SceneCommentResolveRequest",
    "ChoiceResource",
    "MemoryRequestResource",
    "TransitionResource",
    "NarrationOverrideResource",
    "ValidationIssue",
    "SceneValidation",
    "SceneResource",
    "SceneDetailResponse",
    "SceneMutationResponse",
    "SceneDeleteResponse",
]
