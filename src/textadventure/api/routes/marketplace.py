"""Marketplace routes for publishing and discovering community adventures."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..models import (
    MarketplaceEntryListResponse,
    MarketplaceEntryPublishRequest,
    MarketplaceEntryResponse,
    MarketplaceReview,
    MarketplaceReviewCreateRequest,
    MarketplaceReviewListResponse,
)

# Import services (type hints only - actual instances passed at runtime)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import (
        MarketplaceService,
        MarketplaceEntryRecord,
        MarketplaceReviewRecord,
    )


def create_marketplace_router(
    marketplace_service: "MarketplaceService",
) -> APIRouter:
    """Create the marketplace router with injected service dependencies.

    Args:
        marketplace_service: Service for marketplace operations

    Returns:
        Configured APIRouter instance with all marketplace routes
    """
    router = APIRouter()

    # Helper functions (would ideally be in a formatters module)
    def _compute_average_rating(
        reviews: list["MarketplaceReviewRecord"],
    ) -> float | None:
        """Compute average rating from reviews."""
        if not reviews:
            return None
        total = sum(review.rating for review in reviews)
        return total / len(reviews)

    def _sort_reviews_newest_first(
        reviews: list["MarketplaceReviewRecord"],
    ) -> list["MarketplaceReviewRecord"]:
        """Sort reviews by creation date, newest first."""
        return sorted(reviews, key=lambda r: r.created_at, reverse=True)

    def _build_marketplace_review(
        record: "MarketplaceReviewRecord",
    ) -> MarketplaceReview:
        """Build marketplace review resource from record."""
        return MarketplaceReview(
            reviewer_id=record.reviewer_id,
            rating=record.rating,
            comment=record.comment,
            created_at=record.created_at,
        )

    def _build_marketplace_response(
        record: "MarketplaceEntryRecord",
    ) -> MarketplaceEntryResponse:
        """Build marketplace entry response from record."""
        from ..models import MarketplaceEntryResponse as Response

        return Response(
            identifier=record.identifier,
            title=record.title,
            description=record.description,
            author_id=record.author_id,
            tags=record.tags,
            published_at=record.published_at,
            schema_version=record.schema_version,
            scenes=record.scenes,
            reviews=[_build_marketplace_review(r) for r in record.reviews],
        )

    # Marketplace Routes

    @router.get(
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
            return marketplace_service.list_entries(
                search=search,
                tag=tag,
                page=page,
                page_size=page_size,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.get(
        "/api/marketplace/entries/{entry_id}",
        response_model=MarketplaceEntryResponse,
        tags=["Marketplace"],
    )
    def get_marketplace_entry(entry_id: str) -> MarketplaceEntryResponse:
        try:
            record = marketplace_service.get_entry(entry_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_marketplace_response(record)

    @router.get(
        "/api/marketplace/entries/{entry_id}/reviews",
        response_model=MarketplaceReviewListResponse,
        tags=["Marketplace"],
    )
    def list_marketplace_entry_reviews(
        entry_id: str,
    ) -> MarketplaceReviewListResponse:
        try:
            record = marketplace_service.get_entry(entry_id)
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

    @router.post(
        "/api/marketplace/entries",
        response_model=MarketplaceEntryResponse,
        status_code=201,
        tags=["Marketplace"],
    )
    def publish_marketplace_entry(
        payload: MarketplaceEntryPublishRequest,
    ) -> MarketplaceEntryResponse:
        try:
            record = marketplace_service.publish_entry(payload)
        except Exception as exc:
            # Check for MarketplaceEntryAlreadyExistsError
            if type(exc).__name__ == "MarketplaceEntryAlreadyExistsError":
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            elif isinstance(exc, ValueError):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            elif isinstance(exc, RuntimeError):
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            raise

        return _build_marketplace_response(record)

    @router.post(
        "/api/marketplace/entries/{entry_id}/reviews",
        response_model=MarketplaceReview,
        status_code=201,
        tags=["Marketplace"],
    )
    def create_marketplace_entry_review(
        entry_id: str, payload: MarketplaceReviewCreateRequest
    ) -> MarketplaceReview:
        try:
            _, review = marketplace_service.add_review(entry_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return _build_marketplace_review(review)

    return router
