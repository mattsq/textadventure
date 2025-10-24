"""Project management routes for projects, collaborators, and templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response  # type: ignore[attr-defined]

from ..models import (
    AdventureProjectDetailResponse,
    AdventureProjectListResponse,
    AdventureProjectTemplateListResponse,
    ProjectCollaboratorListResponse,
    ProjectCollaboratorUpdateRequest,
    ProjectTemplateInstantiateRequest,
    ProjectPermissionError,
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
                status_code=404,
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
                status_code=404,
                detail="Project service is not configured.",
            )
        try:
            return project_service.get_project(identifier=project_id)
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
                status_code=404,
                detail="Project service is not configured.",
            )
        try:
            archive = project_service.export_project(identifier=project_id)
            headers = {
                "content-disposition": f'attachment; filename="{archive.filename}"',
                "content-length": str(len(archive.content)),
                "x-textadventure-project-id": archive.project_id,
                "x-textadventure-project-version": archive.version_id,
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
                status_code=404,
                detail="Project service is not configured.",
            )
        try:
            return project_service.list_project_collaborators(identifier=project_id)
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
                status_code=404,
                detail="Project service is not configured.",
            )
        try:
            return project_service.replace_project_collaborators(
                identifier=project_id,
                collaborators=payload.collaborators,
                acting_user_id=acting_user_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
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
                status_code=404,
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
                status_code=404,
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
