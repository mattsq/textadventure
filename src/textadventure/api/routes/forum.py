"""Forum routes for community discussions and threads."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    ForumPostCreateRequest,
    ForumPostResource,
    ForumThreadCreateRequest,
    ForumThreadDetail,
    ForumThreadListResponse,
)

# Import services (type hints only - actual instances passed at runtime)
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app import ForumThreadRecord, ForumPostRecord


def create_forum_router(
    forum_service: Any,
) -> APIRouter:
    """Create the forum router with injected service dependencies.

    Args:
        forum_service: Service for forum operations

    Returns:
        Configured APIRouter instance with all forum routes
    """
    router = APIRouter()

    # Helper functions (would ideally be in a formatters module)
    def _build_forum_post(record: "ForumPostRecord") -> ForumPostResource:
        """Build forum post resource from record."""
        return ForumPostResource(
            id=record.identifier,
            author=record.author,
            body=record.body,
            created_at=record.created_at,
        )

    def _build_forum_thread_detail(record: "ForumThreadRecord") -> ForumThreadDetail:
        """Build forum thread detail from record."""
        posts = [_build_forum_post(post) for post in record.posts]
        return ForumThreadDetail(
            id=record.identifier,
            title=record.title,
            author=record.author,
            created_at=record.created_at,
            updated_at=record.updated_at,
            post_count=len(record.posts),
            posts=posts,
        )

    # Forum Routes

    @router.get(
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
            return forum_service.list_threads(page=page, page_size=page_size)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.post(
        "/api/forums/threads",
        response_model=ForumThreadDetail,
        status_code=201,
        tags=["Forums"],
    )
    def create_forum_thread(
        payload: ForumThreadCreateRequest,
    ) -> ForumThreadDetail:
        try:
            record = forum_service.create_thread(payload)
        except Exception as exc:
            # Check for ForumThreadAlreadyExistsError
            if type(exc).__name__ == "ForumThreadAlreadyExistsError":
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            elif isinstance(exc, ValueError):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            elif isinstance(exc, RuntimeError):
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            raise

        return _build_forum_thread_detail(record)

    @router.get(
        "/api/forums/threads/{thread_id}",
        response_model=ForumThreadDetail,
        tags=["Forums"],
    )
    def get_forum_thread(thread_id: str) -> ForumThreadDetail:
        try:
            record = forum_service.get_thread(thread_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_forum_thread_detail(record)

    @router.post(
        "/api/forums/threads/{thread_id}/posts",
        response_model=ForumPostResource,
        status_code=201,
        tags=["Forums"],
    )
    def create_forum_post(
        thread_id: str, payload: ForumPostCreateRequest
    ) -> ForumPostResource:
        try:
            post = forum_service.add_post(thread_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_forum_post(post)

    return router
