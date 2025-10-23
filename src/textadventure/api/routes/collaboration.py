"""Collaboration-related routes for sessions and inline scene comments."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query  # type: ignore[attr-defined]

from ..models import (
    ProjectCollaborationSessionListResponse,
    ProjectCollaborationSessionRequest,
    ProjectPermissionError,
    SceneCommentReplyRequest,
    SceneCommentResolveRequest,
    SceneCommentThreadCreateRequest,
    SceneCommentThreadListResponse,
    SceneCommentThreadResource,
)
from ..models.scene import SceneCommentLocationType


def create_collaboration_router(
    *,
    project_service: Any | None = None,
    comment_service: Any | None = None,
) -> APIRouter:
    """Create the collaboration router with injected service dependencies.

    Args:
        project_service: Service handling project collaboration sessions.
        comment_service: Service managing inline scene comment threads.

    Returns:
        Configured APIRouter instance with collaboration endpoints.
    """

    router = APIRouter()

    # Collaboration session routes -------------------------------------------------

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
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            return project_service.list_collaboration_sessions(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
                "Identifier of the collaborator performing the join or heartbeat."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            return project_service.touch_collaboration_session(
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
                "Identifier of the collaborator performing the session termination."
            ),
        ),
    ) -> ProjectCollaborationSessionListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            return project_service.end_collaboration_session(
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

    # Scene comment routes ---------------------------------------------------------

    @router.get(
        "/api/projects/{project_id}/scenes/{scene_id}/comments",
        response_model=SceneCommentThreadListResponse,
        tags=["Scene Comments"],
    )
    def list_scene_comment_threads(
        project_id: str,
        scene_id: str,
        location_type: SceneCommentLocationType | None = Query(
            None,
            description="Optional location type filter when listing comment threads.",
        ),
        choice_command: str | None = Query(
            None,
            description="Optional transition command filter for comment threads.",
        ),
    ) -> SceneCommentThreadListResponse:
        if comment_service is None:
            raise HTTPException(
                status_code=404,
                detail="Scene comment functionality is not configured for this deployment.",
            )

        try:
            return comment_service.list_threads(
                project_id,
                scene_id,
                location_type=location_type,
                choice_command=choice_command,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post(
        "/api/projects/{project_id}/scenes/{scene_id}/comments",
        response_model=SceneCommentThreadResource,
        status_code=201,
        tags=["Scene Comments"],
    )
    def create_scene_comment_thread(
        project_id: str,
        scene_id: str,
        payload: SceneCommentThreadCreateRequest,
        acting_user_id: str | None = Query(
            None,
            description="Identifier of the collaborator creating the comment thread.",
        ),
    ) -> SceneCommentThreadResource:
        if comment_service is None:
            raise HTTPException(
                status_code=404,
                detail="Scene comment functionality is not configured for this deployment.",
            )

        try:
            return comment_service.create_thread(
                project_id,
                scene_id,
                location=payload.location,
                body=payload.body,
                author_id=payload.author_id or acting_user_id,
                author_display_name=payload.author_display_name,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post(
        "/api/projects/{project_id}/scenes/{scene_id}/comments/{thread_id}/replies",
        response_model=SceneCommentThreadResource,
        status_code=201,
        tags=["Scene Comments"],
    )
    def add_scene_comment_reply(
        project_id: str,
        scene_id: str,
        thread_id: str,
        payload: SceneCommentReplyRequest,
        acting_user_id: str | None = Query(
            None,
            description="Identifier of the collaborator adding the inline comment reply.",
        ),
    ) -> SceneCommentThreadResource:
        if comment_service is None:
            raise HTTPException(
                status_code=404,
                detail="Scene comment functionality is not configured for this deployment.",
            )

        try:
            return comment_service.add_comment(
                project_id,
                scene_id,
                thread_id,
                body=payload.body,
                author_id=payload.author_id or acting_user_id,
                author_display_name=payload.author_display_name,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post(
        "/api/projects/{project_id}/scenes/{scene_id}/comments/{thread_id}/resolution",
        response_model=SceneCommentThreadResource,
        tags=["Scene Comments"],
    )
    def set_scene_comment_resolution(
        project_id: str,
        scene_id: str,
        thread_id: str,
        payload: SceneCommentResolveRequest,
        acting_user_id: str | None = Query(
            None,
            description="Identifier of the collaborator updating the comment thread resolution state.",
        ),
    ) -> SceneCommentThreadResource:
        if comment_service is None:
            raise HTTPException(
                status_code=404,
                detail="Scene comment functionality is not configured for this deployment.",
            )

        try:
            return comment_service.set_resolution(
                project_id,
                scene_id,
                thread_id,
                resolved=payload.resolved,
                acting_user_id=acting_user_id,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ProjectPermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
