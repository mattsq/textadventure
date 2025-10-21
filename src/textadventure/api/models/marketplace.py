"""Pydantic models for marketplace functionality.

This module defines the request and response models for the marketplace API,
including marketplace entries, reviews, and publishing functionality.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping, Sequence

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from .common import Pagination


# Constants
CURRENT_SCENE_SCHEMA_VERSION = 2
_MARKETPLACE_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


# Helper functions
def _normalise_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError("Profile text must be provided as a string.")

    trimmed = value.strip()
    return trimmed or None


def _normalise_marketplace_identifier(identifier: str) -> str:
    if not isinstance(identifier, str):
        raise ValueError("Marketplace identifier must be provided as a string.")

    slug = identifier.strip().casefold()
    if not slug:
        raise ValueError("Marketplace identifier must be a non-empty string.")

    if not _MARKETPLACE_IDENTIFIER_PATTERN.fullmatch(slug):
        raise ValueError(
            "Marketplace identifier must only contain lowercase letters, numbers, and hyphens."
        )

    return slug


# Models
class MarketplaceEntrySummary(BaseModel):
    """Summary metadata describing a published marketplace entry."""

    id: str = Field(..., description="Stable identifier for the marketplace entry.")
    title: str = Field(..., description="Display title for the shared adventure.")
    description: str | None = Field(
        None,
        description="Optional short description supplied by the publisher.",
    )
    author: str | None = Field(
        None,
        description="Optional credit or author name provided by the publisher.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Normalised discovery tags associated with the entry.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp indicating when the entry was published."
    )
    scene_count: int = Field(
        ..., ge=0, description="Number of scene definitions contained in the entry."
    )
    average_rating: float | None = Field(
        None,
        ge=1.0,
        le=5.0,
        description="Average rating for the entry if any reviews have been submitted.",
    )
    review_count: int = Field(
        0,
        ge=0,
        description="Number of reviews that have been recorded for the entry.",
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class MarketplaceReview(BaseModel):
    """Representation of a marketplace review visible through the API."""

    reviewer: str | None = Field(
        None,
        description="Optional reviewer name supplied alongside the rating.",
    )
    rating: int = Field(..., ge=1, le=5, description="Rating value between 1 and 5.")
    comment: str | None = Field(
        None,
        description="Optional free-form feedback accompanying the rating.",
    )
    created_at: datetime = Field(
        ..., description="Timestamp describing when the review was submitted."
    )

    @field_serializer("created_at")
    def _serialise_created_at(self, value: datetime) -> str:
        return value.isoformat()


class MarketplaceEntryListResponse(BaseModel):
    """Response envelope describing marketplace entries."""

    data: list[MarketplaceEntrySummary] = Field(
        default_factory=list,
        description="Collection of marketplace entries ordered by recency.",
    )
    pagination: Pagination


class MarketplaceReviewCreateRequest(BaseModel):
    """Request payload for submitting a review for a marketplace entry."""

    reviewer: str | None = Field(
        None,
        description="Optional reviewer name that will be displayed alongside the review.",
    )
    rating: int = Field(..., ge=1, le=5, description="Rating value between 1 and 5.")
    comment: str | None = Field(
        None,
        description="Optional free-form comment providing additional feedback.",
    )

    @field_validator("reviewer", "comment", mode="before")
    @classmethod
    def _normalise_optional_text_field(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        raise TypeError("Value must be a string or null.")


class MarketplaceReviewListResponse(BaseModel):
    """Response envelope describing reviews for a marketplace entry."""

    data: list[MarketplaceReview] = Field(
        default_factory=list,
        description="Collection of reviews ordered by submission time (newest first).",
    )
    average_rating: float | None = Field(
        None,
        ge=1.0,
        le=5.0,
        description="Average rating across all submitted reviews.",
    )
    review_count: int = Field(
        0,
        ge=0,
        description="Number of reviews that have been submitted.",
    )


class MarketplaceEntryPublishRequest(BaseModel):
    """Request payload for publishing an adventure to the marketplace."""

    identifier: str | None = Field(
        None,
        description=(
            "Optional identifier to assign to the entry. If omitted, an identifier "
            "is generated from the title."
        ),
    )
    title: str = Field(..., description="Display title for the shared adventure.")
    description: str | None = Field(
        None, description="Optional short description of the adventure."
    )
    author: str | None = Field(
        None, description="Optional credit or author name for the adventure."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Optional discovery tags to associate with the entry.",
    )
    scenes: Mapping[str, Any] = Field(
        ...,
        description=(
            "Scene definitions that should be bundled with the marketplace entry."
        ),
    )
    schema_version: int = Field(
        ..., ge=1, description="Scene schema version describing the dataset."
    )

    @field_validator("identifier")
    @classmethod
    def _normalise_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalise_marketplace_identifier(value)

    @field_validator("title")
    @classmethod
    def _normalise_title(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Title must be provided as a string.")
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Title must be a non-empty string.")
        return trimmed

    @field_validator("description")
    @classmethod
    def _normalise_description(cls, value: str | None) -> str | None:
        return _normalise_optional_text(value)

    @field_validator("author")
    @classmethod
    def _normalise_author(cls, value: str | None) -> str | None:
        return _normalise_optional_text(value)

    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, value: Sequence[str]) -> list[str]:
        if isinstance(value, str):
            raise ValueError("Tags must be provided as an iterable of strings.")
        if value is None:
            return []
        seen: set[str] = set()
        normalised: list[str] = []
        for tag in value:
            if not isinstance(tag, str):
                raise ValueError("Tags must be provided as strings.")
            candidate = _normalise_optional_text(tag) or ""
            if not candidate:
                continue
            slug = candidate.casefold()
            if slug in seen:
                continue
            seen.add(slug)
            normalised.append(slug)
        return normalised

    @field_validator("scenes")
    @classmethod
    def _validate_scenes(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError("Scenes must be provided as a mapping.")
        return value

    @model_validator(mode="after")
    def _validate_schema_version(self) -> "MarketplaceEntryPublishRequest":
        if self.schema_version != CURRENT_SCENE_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must match the current scene schema version."
            )
        return self


__all__ = [
    "CURRENT_SCENE_SCHEMA_VERSION",
    "MarketplaceEntrySummary",
    "MarketplaceReview",
    "MarketplaceEntryListResponse",
    "MarketplaceReviewCreateRequest",
    "MarketplaceReviewListResponse",
    "MarketplaceEntryPublishRequest",
]
