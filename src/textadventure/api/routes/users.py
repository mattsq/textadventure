"""User management routes for profiles and authentication."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException  # type: ignore[attr-defined]

from ..models import (
    UserProfileCreateRequest,
    UserProfileListResponse,
    UserProfileResource,
    UserProfileUpdateRequest,
)


def create_users_router(
    user_service: Any | None = None,
) -> APIRouter:
    """Create the users router with injected service dependencies.

    Args:
        user_service: Optional service for user management operations

    Returns:
        Configured APIRouter instance with all user routes
    """
    router = APIRouter()

    # User Routes

    @router.get(
        "/api/users",
        response_model=UserProfileListResponse,
        tags=["Users"],
    )
    def list_users() -> UserProfileListResponse:
        if user_service is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user_service.list_users()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/users/{user_id}",
        response_model=UserProfileResource,
        tags=["Users"],
    )
    def get_user(user_id: str) -> UserProfileResource:
        if user_service is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user_service.get_user(user_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/users",
        response_model=UserProfileResource,
        status_code=201,
        tags=["Users"],
    )
    def create_user(payload: UserProfileCreateRequest) -> UserProfileResource:
        if user_service is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        try:
            return user_service.create_user(
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

    @router.put(
        "/api/users/{user_id}",
        response_model=UserProfileResource,
        tags=["Users"],
    )
    def update_user(
        user_id: str, payload: UserProfileUpdateRequest
    ) -> UserProfileResource:
        if user_service is None:
            raise HTTPException(404, "User management endpoints are not enabled.")

        update_kwargs: dict[str, Any] = {}
        if "display_name" in payload.model_fields_set:
            update_kwargs["display_name"] = payload.display_name
        if "email" in payload.model_fields_set:
            update_kwargs["email"] = payload.email
        if "bio" in payload.model_fields_set:
            update_kwargs["bio"] = payload.bio

        try:
            return user_service.update_user(user_id, **update_kwargs)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return router
