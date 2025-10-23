"""Scene management routes for CRUD, validation, search, and branching."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence, cast, get_args

from fastapi import APIRouter, HTTPException, Query  # type: ignore[attr-defined]

from ...search import FieldType, SearchResults
from ..models import (
    CollaboratorRole,
    ExportFormat,
    FormattedJSONResponse,
    ProjectPermissionError,
    SceneBranchListResponse,
    SceneBranchPlanRequest,
    SceneBranchPlanResponse,
    SceneCreateRequest,
    SceneDeleteResponse,
    SceneDetailResponse,
    SceneDiffRequest,
    SceneDiffResponse,
    SceneImportRequest,
    SceneImportResponse,
    SceneListResponse,
    SceneMutationResponse,
    SceneReferenceListResponse,
    SceneRollbackRequest,
    SceneRollbackResponse,
    SceneSearchResponse,
    SceneUpdateRequest,
    SceneValidationResponse,
    TextSpanResource,
    FieldMatchResource,
    SceneSearchResultResource,
    SceneBranchDetailResponse,
    SceneGraphResponse,
    ValidationStatus,
)

# Import services (type hints only - actual instances passed at runtime)
from typing import Any


# Helper functions (standalone, can be used by routes)


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


def create_scenes_router(
    scene_service: Any,
    project_service: Any | None = None,
    *,
    active_scene_path: Path | None = None,
) -> APIRouter:
    """Create the scenes router with injected service dependencies.

    Args:
        scene_service: Service for scene CRUD and validation operations
        project_service: Optional service for project/permission operations
        active_scene_path: Path to the active scene dataset for permission checks

    Returns:
        Configured APIRouter instance with all scene-related routes
    """
    router = APIRouter()

    def _enforce_scene_permission(
        acting_user_id: str | None,
        *,
        allowed_roles: Sequence[CollaboratorRole],
        action: str,
    ) -> None:
        """Enforce permission checks for scene mutations."""
        if project_service is None or active_scene_path is None:
            return

        try:
            project_service.require_scene_dataset_permission(
                scene_path=active_scene_path,
                acting_user_id=acting_user_id,
                allowed_roles=allowed_roles,
                action=action,
            )
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    def _handle_scene_export(
        ids_param: str | None, format_param: ExportFormat
    ) -> FormattedJSONResponse:
        """Handle scene export with format and filtering."""
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
            export = scene_service.export_scenes(ids=parsed_ids)
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
        """Handle scene import validation."""
        try:
            return scene_service.validate_import_payload(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                start_scene=payload.start_scene,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Scene CRUD Routes

    @router.get(
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
            return scene_service.list_scene_summaries(
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

    @router.get(
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
            return scene_service.get_scene_detail(
                scene_id=scene_id, include_validation=include_validation
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
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
            return scene_service.create_scene(
                scene_id=payload.id,
                scene=payload.scene,
                schema_version=payload.schema_version,
                expected_version_id=payload.expected_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.put(
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
            return scene_service.update_scene(
                scene_id=scene_id,
                scene=payload.scene,
                schema_version=payload.schema_version,
                expected_version_id=payload.expected_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.delete(
        "/api/scenes/{scene_id}",
        response_model=SceneDeleteResponse,
        tags=["Scenes"],
    )
    def delete_scene_endpoint(
        scene_id: str,
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
            return scene_service.delete_scene(scene_id=scene_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/scenes/{scene_id}/references",
        response_model=SceneReferenceListResponse,
        tags=["Scenes"],
    )
    def list_scene_references(scene_id: str) -> SceneReferenceListResponse:
        try:
            return scene_service.list_scene_references(scene_id=scene_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Scene Graph and Validation Routes

    @router.get(
        "/api/scenes/graph",
        response_model=SceneGraphResponse,
        tags=["Scenes"],
    )
    @router.get(
        "/scenes/graph",
        response_model=SceneGraphResponse,
        tags=["Scenes"],
    )
    def get_scene_graph(
        *,
        start_scene: str | None = Query(
            None,
            description=(
                "Identifier of the scene to use as the adventure starting point when "
                "computing reachability metadata."
            ),
        ),
    ) -> SceneGraphResponse:
        try:
            return scene_service.get_scene_graph(start_scene=start_scene)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Search Route

    @router.get(
        "/api/search",
        response_model=SceneSearchResponse,
        tags=["Search"],
    )
    def search_scenes(
        query: str = Query(
            ..., description="The search phrase to locate in scene text."
        ),
        field_types: str | None = Query(
            None,
            description=(
                "Comma-separated field types to search within "
                "(e.g., 'description,choice_text,narration')."
            ),
        ),
        validation_statuses: str | None = Query(
            None,
            description=(
                "Comma-separated validation status filters " "(e.g., 'valid,warning')."
            ),
        ),
        limit: int = Query(100, ge=1, le=500),
    ) -> SceneSearchResponse:
        try:
            parsed_field_types = _parse_field_type_filters(field_types)
            parsed_validation_statuses = _parse_validation_filters(validation_statuses)
            results = scene_service.search_scene_text(
                query=query,
                field_types=parsed_field_types,
                validation_statuses=parsed_validation_statuses,
            )
            return _build_search_response(results, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/scenes/validate",
        response_model=SceneValidationResponse,
        tags=["Scenes"],
    )
    def validate_scenes(
        *,
        start_scene: str | None = Query(
            None,
            description=(
                "Identifier of the adventure starting scene for reachability analysis."
            ),
        ),
    ) -> SceneValidationResponse:
        try:
            return scene_service.validate_scenes(start_scene=start_scene)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Export and Import Routes

    @router.get(
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
                "Options: 'minified' or 'pretty'."
            ),
        ),
    ) -> FormattedJSONResponse:
        return _handle_scene_export(ids, format)

    @router.get(
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
                "Options: 'minified' or 'pretty'."
            ),
        ),
    ) -> FormattedJSONResponse:
        return _handle_scene_export(ids, format)

    @router.post(
        "/api/import/scenes",
        response_model=SceneImportResponse,
        tags=["Scenes"],
    )
    def import_scenes_legacy(payload: SceneImportRequest) -> SceneImportResponse:
        return _handle_scene_import(payload)

    @router.post(
        "/api/scenes/import",
        response_model=SceneImportResponse,
        tags=["Scenes"],
    )
    def import_scenes(payload: SceneImportRequest) -> SceneImportResponse:
        return _handle_scene_import(payload)

    @router.post(
        "/api/scenes/rollback",
        response_model=SceneRollbackResponse,
        tags=["Scenes"],
    )
    def plan_rollback(payload: SceneRollbackRequest) -> SceneRollbackResponse:
        try:
            return scene_service.plan_rollback(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                generated_at=payload.generated_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/scenes/diff",
        response_model=SceneDiffResponse,
        tags=["Scenes"],
    )
    def diff_scenes(payload: SceneDiffRequest) -> SceneDiffResponse:
        try:
            return scene_service.diff_scenes(
                scenes=payload.scenes,
                schema_version=payload.schema_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Branch Routes

    @router.get(
        "/api/scenes/branches",
        response_model=SceneBranchListResponse,
        tags=["Scene Branches"],
    )
    def list_branches() -> SceneBranchListResponse:
        try:
            return scene_service.list_branches()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/scenes/branches/{branch_id}",
        response_model=SceneBranchDetailResponse,
        tags=["Scene Branches"],
    )
    def get_branch(branch_id: str) -> SceneBranchDetailResponse:
        try:
            return scene_service.get_branch(identifier=branch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/scenes/branches",
        response_model=SceneBranchDetailResponse,
        status_code=201,
        tags=["Scene Branches"],
    )
    def create_branch(
        payload: SceneBranchPlanRequest,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the branch mutation."
            ),
        ),
    ) -> SceneBranchDetailResponse:
        _enforce_scene_permission(
            acting_user_id,
            allowed_roles=(CollaboratorRole.OWNER, CollaboratorRole.EDITOR),
            action="create scene branches",
        )
        try:
            return scene_service.create_branch(
                branch_name=payload.branch_name,
                scenes=payload.scenes,
                schema_version=payload.schema_version,
                generated_at=payload.generated_at,
                expected_base_version=payload.base_version_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.delete(
        "/api/scenes/branches/{branch_id}",
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
            action="delete scene branches",
        )
        try:
            scene_service.delete_branch(identifier=branch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/scenes/branches/plan",
        response_model=SceneBranchPlanResponse,
        tags=["Scene Branches"],
    )
    def plan_branch(payload: SceneBranchPlanRequest) -> SceneBranchPlanResponse:
        try:
            return scene_service.plan_branch(
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

    return router
