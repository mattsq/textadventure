"""Project management routes for projects, assets, collaborators, and templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response  # type: ignore[attr-defined]

from ..models import (
    AdventureProjectDetailResponse,
    AdventureProjectListResponse,
    AdventureProjectTemplateListResponse,
    ProjectAssetListResponse,
    ProjectAssetUploadRequest,
    ProjectCollaborationSessionListResponse,
    ProjectCollaborationSessionRequest,
    ProjectCollaboratorListResponse,
    ProjectCollaboratorUpdateRequest,
    ProjectTemplateInstantiateRequest,
)

# Import services (type hints only - actual instances passed at runtime)
from typing import Any


def create_projects_router(
    project_service: Any | None = None,
    template_service: Any | None = None,
) -> APIRouter:
    """Create the projects router with injected service dependencies.

    Args:
        project_service: Service for project and asset operations
        template_service: Optional service for template operations

    Returns:
        Configured APIRouter instance with all project-related routes
    """
    router = APIRouter()

    # Project Routes

    @router.get(
        "/api/projects",
        response_model=AdventureProjectListResponse,
        tags=["Projects"],
    )
    def list_projects() -> AdventureProjectListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.list_projects()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/projects/{project_id}",
        response_model=AdventureProjectDetailResponse,
        tags=["Projects"],
    )
    def get_project(project_id: str) -> AdventureProjectDetailResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.get_project(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/projects/{project_id}/export",
        response_model=None,
        tags=["Projects"],
    )
    def export_project_archive(project_id: str) -> Response:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            archive = project_service.export_project(project_id=project_id)
            headers = {
                "content-disposition": f"attachment; filename={archive.filename}",
                "content-length": str(len(archive.content)),
                "x-textadventure-project-id": archive.project_id,
                "x-textadventure-project-version": archive.version,
                "x-textadventure-project-checksum": archive.checksum,
            }
            return Response(
                content=archive.content,
                media_type="application/zip",
                headers=headers,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Asset Routes

    @router.get(
        "/api/projects/{project_id}/assets",
        response_model=ProjectAssetListResponse,
        tags=["Projects"],
    )
    def list_project_assets(project_id: str) -> ProjectAssetListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.list_project_assets(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        response_model=None,
        tags=["Projects"],
    )
    def get_project_asset(project_id: str, asset_path: str) -> Response:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            asset = project_service.fetch_project_asset(
                project_id=project_id,
                asset_path=asset_path,
            )
            return Response(
                content=asset.content,
                media_type=asset.media_type,
                headers=asset.headers,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.put(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        response_model=ProjectAssetListResponse,
        tags=["Projects"],
    )
    def upload_project_asset(
        project_id: str,
        asset_path: str,
        payload: ProjectAssetUploadRequest,
        acting_user_id: str | None = Query(
            None,
            description=("Identifier of the collaborator performing the asset upload."),
        ),
    ) -> ProjectAssetListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            content = payload.decoded_content()
            project_service.store_project_asset(
                project_id=project_id,
                asset_path=asset_path,
                content=content,
                acting_user_id=acting_user_id,
            )
            return project_service.list_project_assets(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.delete(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        response_model=ProjectAssetListResponse,
        tags=["Projects"],
    )
    def delete_project_asset(
        project_id: str,
        asset_path: str,
        acting_user_id: str | None = Query(
            None,
            description=(
                "Identifier of the collaborator performing the asset deletion."
            ),
        ),
    ) -> ProjectAssetListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            project_service.delete_project_asset(
                project_id=project_id,
                asset_path=asset_path,
                acting_user_id=acting_user_id,
            )
            return project_service.list_project_assets(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Collaborator Routes

    @router.get(
        "/api/projects/{project_id}/collaborators",
        response_model=ProjectCollaboratorListResponse,
        tags=["Projects"],
    )
    def list_project_collaborators(
        project_id: str,
    ) -> ProjectCollaboratorListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.list_project_collaborators(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.put(
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
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.replace_project_collaborators(
                project_id=project_id,
                collaborators=payload.collaborators,
                acting_user_id=acting_user_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Collaboration Session Routes

    @router.get(
        "/api/projects/{project_id}/collaboration/sessions",
        response_model=ProjectCollaborationSessionListResponse,
        tags=["Projects"],
    )
    def list_project_collaboration_sessions(
        project_id: str,
    ) -> ProjectCollaborationSessionListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            return project_service.list_collaboration_sessions(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
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
                "Identifier of the collaborator performing the session update."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            project_service.touch_collaboration_session(
                project_id=project_id,
                acting_user_id=acting_user_id,
                session_id=payload.session_id,
                scene_id=payload.scene_id,
                ttl_seconds=payload.ttl_seconds,
            )
            return project_service.list_collaboration_sessions(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.delete(
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
                "Identifier of the collaborator performing the session deletion."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project service is not configured.",
            )
        try:
            project_service.end_collaboration_session(
                project_id=project_id,
                session_id=session_id,
                acting_user_id=acting_user_id,
            )
            return project_service.list_collaboration_sessions(project_id=project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Project Template Routes

    @router.get(
        "/api/project-templates",
        response_model=AdventureProjectTemplateListResponse,
        tags=["Project Templates"],
    )
    def list_project_templates() -> AdventureProjectTemplateListResponse:
        if template_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project template service is not configured.",
            )
        try:
            return template_service.list_templates()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/project-templates/{template_id}/instantiate",
        response_model=AdventureProjectDetailResponse,
        status_code=201,
        tags=["Project Templates"],
    )
    def instantiate_project_template(
        template_id: str,
        payload: ProjectTemplateInstantiateRequest,
    ) -> AdventureProjectDetailResponse:
        if template_service is None:
            raise HTTPException(
                status_code=501,
                detail="Project template service is not configured.",
            )
        try:
            return template_service.instantiate_template(
                template_id=template_id,
                project_id=payload.project_id,
                name=payload.name,
                description=payload.description,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return router
