"""FastAPI application exposing read-only scene management endpoints."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Iterable, Mapping, Literal, Sequence, cast, get_args

from fastapi import FastAPI, HTTPException, Query
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


class SceneExportResponse(BaseModel):
    """Payload containing a full export of the current scene dataset."""

    generated_at: datetime
    scenes: dict[str, Any]

    @field_serializer("generated_at")
    def _serialise_generated_at(self, value: datetime) -> str:
        return value.isoformat()


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

        quality_report = assess_adventure_quality(scene_mapping)
        reachability_report = compute_scene_reachability(
            scene_mapping, start_scene=start_scene
        )
        item_flow_report = analyse_item_flow(scene_mapping)

        return SceneValidationReport(
            generated_at=dataset_timestamp,
            quality=_build_quality_resource(quality_report),
            reachability=_build_reachability_resource(reachability_report),
            item_flow=_build_item_flow_resource(item_flow_report),
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

        return SceneExportResponse(
            generated_at=dataset_timestamp,
            scenes=serialisable,
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

    @app.get("/api/export/scenes", response_model=SceneExportResponse)
    def export_scenes(
        ids: str | None = Query(
            None,
            description=(
                "Comma-separated list of scene identifiers to export. "
                "When omitted, the full dataset is returned."
            ),
        ),
    ) -> SceneExportResponse:
        try:
            parsed_ids = _parse_scene_id_filter(ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            return service.export_scenes(ids=parsed_ids)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
