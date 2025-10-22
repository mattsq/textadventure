"""Routes for managing assets associated with adventure projects."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response  # type: ignore[attr-defined]

from ..models import (
    ProjectAssetListResponse,
    ProjectAssetResource,
    ProjectAssetUploadRequest,
    ProjectPermissionError,
)


def create_assets_router(project_service: Any | None = None) -> APIRouter:
    """Create a router exposing project asset management endpoints."""

    router = APIRouter()

    @router.get(
        "/api/projects/{project_id}/assets",
        response_model=ProjectAssetListResponse,
        tags=["Projects"],
    )
    def list_project_assets(project_id: str) -> ProjectAssetListResponse:
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            return project_service.list_project_assets(project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/projects/{project_id}/assets/{asset_path:path}",
        tags=["Projects"],
    )
    def get_project_asset(project_id: str, asset_path: str) -> Response:
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            asset = project_service.fetch_project_asset(project_id, asset_path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        headers = {"content-disposition": f'attachment; filename="{asset.filename}"'}
        media_type = asset.content_type or "application/octet-stream"
        return Response(content=asset.content, media_type=media_type, headers=headers)

    @router.put(
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
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            content = payload.decoded_content()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            return project_service.store_project_asset(
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

    @router.delete(
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
        if project_service is None:
            raise HTTPException(
                status_code=404,
                detail="Project management endpoints are not enabled.",
            )

        try:
            project_service.delete_project_asset(
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

    return router


__all__ = ["create_assets_router"]
